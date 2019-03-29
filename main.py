from typing import Tuple, List
import contractions
import stanfordnlp
import json
import functools
import spacy
import os
from spacy.symbols import PRON
import string
from neo4j import GraphDatabase
from stanfordnlp.server import CoreNLPClient
import urllib.request
import urllib.parse

os.environ['CORENLP_HOME'] = os.path.join(os.getcwd(), 'stanford-corenlp-full-2018-10-05/')
nlpClient = CoreNLPClient(timeout=30000, memory='16G', output_format='json')

parser = spacy.load('en_core_web_sm')

neo4jUser = 'neo4j'
neo4jPassword = 'password'
neo4jUri = 'bolt://localhost:7687'

postGresBaseURL = 'http://ec2-3-84-24-105.compute-1.amazonaws.com/play/'

play = 'hamlet'

outputFile = 'triples.txt'

def retrieveText(url: str) -> List[Tuple[str, str]]:
    response = urllib.request.urlopen(url)
    playText = eval(response.read())
    return playText

def retrievePlayCharacters() -> List[Tuple[str, str]]:
    global play
    url = urllib.parse.urljoin(postGresBaseURL, play + '/characters')
    return retrieveText(url)

def retrievePlayText() -> List[Tuple[str, str]]:
    global play
    url = urllib.parse.urljoin(postGresBaseURL + 'modern/', play)
    return retrieveText(url)

def preprocessText(playText: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return playText

def substitutePronouns(playText: List[Tuple[str, str]], verbose: bool = False) -> List[Tuple[str, str]]:
    """
    Replaces first and second person personal pronouns with the appropriate speaker.
    Args:
        playText: The text of a play to substitute pronouns in.
    Returns:
        This function returns the play text in the same input format, but with personal pronouns
        replaced by the speaker's name.
    """
    if verbose:
        print('SUBSTITUTE PRONOUNS')
    global parser

    prevchar = None
    currchar = None

    for i, (character, dialogue) in enumerate(playText):
        currchar = string.capwords(character)
        doc = parser(contractions.fix(dialogue))
        subs = ''
        for j, word in enumerate(doc):
            if word.pos == PRON and word.lower_ in ['i', 'me']:
                if verbose:
                    print(f'substituting {word.text} to {currchar.capitalize()}')
                subs += word.text_with_ws.replace(word.text, currchar.capitalize())
            elif word.pos == PRON and word.lower_ in ['you', 'thou', 'thee'] and prevchar is not None:
                if verbose:
                    print(f'substituting {word.text} to {prevchar.capitalize()}')
                subs += word.text_with_ws.replace(word.text, prevchar.capitalize())
            else:
                subs += word.text_with_ws

        playText[i] = (character, subs)
        if currchar != prevchar:
            prevchar = currchar

    return playText

def coreferenceResolve(playText: List[Tuple[str, str]], verbose: bool = False) -> List[Tuple[str, str]]:
    """
    Makes API calls to coreNLP using the coreference annotator to resolve coreferences in the play text.
    Args:
        playText: The text of a play to resolve coreferences in.
    Returns:
        This function returns the play text in the same input format, but with coreferences resolved.
    """
    if verbose:
        print('COREFERENCE RESOLUTION')
    global nlpClient
    annotators = ['coref']
    for i, (character, dialogue) in enumerate(playText):
        inputText = dialogue
        if verbose:
            print('Sending original input text to coreNLP: %s' % inputText)

        annotations = nlpClient.annotate(inputText, annotators=annotators)

        # Reconstruct the sentences using the tokens from coreNLP
        tokenizedSentences = [None] * len(annotations['sentences'])
        for j, sentence in enumerate(annotations['sentences']):
            words = [None] * len(sentence['tokens'])
            for tokenDict in sentence['tokens']:
                words[tokenDict['index']-1] = tokenDict['originalText']
            tokenizedSentences[j] = words

        # Resolve in the coreferences by substituting in the representative mention
        for coref in annotations['corefs'].values():
            # Find the representative mention for this coreference group
            repMention = list(filter(lambda v: v['isRepresentativeMention'], coref))[0]
            if verbose:
                print('identified representative mention: %s' % repMention['text'])
            # Substitute every object for the representative mention
            for object in coref:
                if verbose:
                    print('object mention: %s' % object['text'])
                    print('original sentence: %s' % tokenizedSentences[object['sentNum']-1])
                # Remove the original text from the sentence and replace with spaces
                tokenizedSentences[object['sentNum']-1][object['startIndex']-1:object['endIndex']-1] = [' '] * (object['endIndex'] - object['startIndex'])
                # Insert the representative text
                tokenizedSentences[object['sentNum']-1][object['startIndex']-1] = repMention['text']
                if verbose:
                    print('processed sentence: %s' % tokenizedSentences[object['sentNum']-1])
            if verbose:
                print('')

        # Recreate the line of dialogue by concatenating all the tokens
        processedDialogue = ""
        for s in tokenizedSentences:
            # Filter to remove any space tokens from the representative text substitution
            original = functools.reduce(lambda a, b: a + ' ' + b, filter(lambda v: v != ' ', s[:-1]), '')
            original += s[-1]
            processedDialogue += original + ' '

        playText[i] = (character, processedDialogue)

    return playText

def spacy(playText: List[Tuple[str, str]], verbose: bool = False) -> List[Tuple[str, str]]:
    """
    Uses SpaCy's dependency parser to extract patterns that coreNLP may miss and append them to the playText
    Args:
        playText: The text of a play to extract patterns from
    Returns:
        This function returns the play text in the same input format, but with patterns appended to each line.
    """
    global parser
    #> Means go up, < means go down, * means end of pattern
    patterns = [('PROPN>', 'VERB<', 'PROPN*'), ('PROPN>', 'VERB<', 'VERB<', 'PROPN*'), ('PROPN>', 'VERB<', 'ADP<', 'PROPN*')]
    if verbose:
        print('SPACY DEPENDENCY PARSER')
    for i, (character, dialogue) in enumerate(playText):
        expansion = '';
        doc = parser(dialogue)
        #token.text, token.pos_, token.head, token.child
        for token in doc:
            for pattern in patterns:
                result = findPattern(token, pattern, 0, [])
                if len(result) > 0:
                    if verbose:
                        print('found pattern %s with result: ', ''.join(pattern), result)
                    expansion += ' ' + result
        playText[i] = (character, dialogue + expansion)
    return playText

def findPattern(token, pattern, i, curr):
    """
    A recursive method to find patterns of parts of speech in a dependency tree
    Args:
        token: The current token being iterated through
        pattern: An array of parts of speech. > means go up, < means go down, * means end of pattern
        i: The current index of the pattern array
        curr: The current list of tokens to check against self-loops
    Returns:
        This function returns a string of the completed pattern, or an empty string if it can't complete it
    """
    if curr is not None and token in curr:
        return ''
    curr.append(token)
    pos = pattern[i][:-1]
    symbol = pattern[i][-1]
    if token.pos_ != pos:
        return ''
    elif symbol == '*':
        return token.text + '.'
    elif symbol == '>':
        nxt = findPattern(token.head, pattern, i+1, curr)
        del curr[-1]
        if len(nxt) > 0:
            return token.text + ' ' + nxt
        return ''
    else:
        for child in token.children:
            nxt = findPattern(child, pattern, i+1, curr)
            del curr[-1]
            if len(nxt) > 0:
                return token.text + ' ' + nxt
        return ''

def extractRelationships(playText: List[Tuple[str, str]], verbose: bool = False) -> List[Tuple[str, str, str]]:
    """
    Makes API calls to coreNLP using the openIE annotator to extract relationships from the play text.
    Args:
        playText: The text of a play to extract relationships from.
    Returns:
        This function returns a list of triples, where each triple represents a relationship extracted by openIE
    """
    if verbose:
        print('EXTRACTING RELATIONSHIPS')

    global nlpClient
    annotators = ['openie']
    # Extract just the play text
    inputText = functools.reduce(lambda a, b: a + ' ' + b, [l[1] for l in playText])

    relations = []
    for l in playText:
        inputText = l[1]
        if verbose:
            print('Sending input text to coreNLP: %s\n' % inputText)
        annotations = nlpClient.annotate(inputText, annotators=annotators)
        for sentence in annotations['sentences']:
            for result in sentence['openie']:
                relations.append((result['subject'], result['relation'], result['object']))

    # Unwrapped list comprehension is shown below
    # relations = [(result['subject'], result['relation'], result['object']) for sentence in annotations['sentences'] for result in sentence['openie']]
    """
    for sentence in annotations['sentences']:
        for result in sentence['openie']:
            relation = (result['subject'], result['relation'], result['object'])
            relations.append(relation)
    """
    return relations

def postProcess(triples: List[Tuple[str, str, str]], verbose: bool = True) -> List[Tuple[str, str, str]]:
    """
    This function performs some simple post-processing of the triples by
    removing triples that are proper subsets of others. We are removing
    "dominated" relations in the sense that all of their information is
    contained within another relation.
    Args:
        triples: The triples to process
        verbose: True indicates verbose output should be shown.
    Returns:
        This function returns a processed list of relations as triples.
    """
    if verbose:
        print('POST PROCESSING RELATIONS')
        print('%d triples before removing dominated relations' % len(triples))
    characters = retrievePlayCharacters()
    triplesToRemove = set()
    # Remove if [0] does not include a character, if [0] and [2] have the same character, or if [1] has a character.
    for i in range(len(triples)):
        if all(character[0] not in triples[i][0] for character in characters) or \
        any(character[0] in triples[i][0] and character[0] in triples[i][2] for character in characters) or \
        len(triples[i][0].split(' ')) > 1 or any(character[0] in triples[i][1] for character in characters):
            triplesToRemove.add(i)
    # Compare every relation to every other relation
    for i in range(len(triples)):
        for j in range(i+1, len(triples)):
            # If both triples are already being removed we don't need to check
            if i not in triplesToRemove or j not in triplesToRemove:
                # Check if i is dominated by j
                if all(set(a.split()).issubset(b.split()) for a, b in zip(triples[i], triples[j])):
                    if verbose:
                        print('Found domination: "%s" is dominated by "%s"' % (triples[i], triples[j]))
                    triplesToRemove.add(i)
                # Check if j is dominated by i
                elif all(set(a.split()).issubset(b.split()) for a, b in zip(triples[j], triples[i])):
                    if verbose:
                        print('Found domination: "%s" is dominated by "%s"' % (triples[j], triples[i]))
                    triplesToRemove.add(j)

    if verbose:
        print('Removed %d dominated relations. %d relations left after removal' % (len(triplesToRemove), len(triples) - len(triplesToRemove)))

    # Remove the triples at the indices in triplesToRemove
    triples = list(map(lambda i: i[1], filter(lambda v: v[0] not in triplesToRemove, enumerate(triples))))
    return triples

def writeToDB(triples: List[Tuple[str, str, str]], verbose: bool = False) -> None:
    """
    This function accepts relations as triples and writes those triples into Neo4j.
    Args:
        triples: The triples to write to Neo4j
        verbose: True indicates verbose output should be shown.
    Returns:
        A boolean of whether the operation was successful
    """
    if verbose:
        print('Writing %d triples to Neo4j' % len(triples))
    try:
        neo4jDriver = GraphDatabase.driver(neo4jUri, auth=(neo4jUser, neo4jPassword))
        for relation in triples:
            try:
                with neo4jDriver.session() as session:
                    # Create the subject and object if they don't exist
                    createStatments = [
                        "MERGE (%s1:node {name: \"%s\"})" % (strToNodeName(relation[0]), relation[0]),
                        "MERGE (%s2:node {name: \"%s\"})" % (strToNodeName(relation[2]), relation[2]),
                        ]
                    # Connect the two with the relation if the relation isn't already there
                    relationStatement = "MERGE (%s1)-[:%s {r:\"%s\"}]->(%s2)" % (strToNodeName(relation[0]), strToRelationName(relation[1]), relation[1], strToNodeName(relation[2]))
                    fullStatement = '\n'.join(createStatments + [relationStatement])
                    if verbose:
                        print('Processing triple: %s' % str(relation))
                        print(fullStatement)
                    session.run(fullStatement)
            except Exception as e:
                print('Exception while writing triple to Neo4j: %s' % e)
                print('Full statement: %s' % fullStatement)
    except Exception as e:
        print('Exception during write to Neo4j: %s' % e)
        return False
    return True

def strToNodeName(str) -> str:
    """This function converts a string to a valid Neo4j node name."""
    return ''.join(str.replace("'", '').replace('-', '_').replace('.', '').split()).lower()

def strToRelationName(str) -> str:
    """This function converts a string to a valid Neo4j node name."""
    return str.replace(' ', '_').replace("'", '').replace('-', '_').replace('.', '')

def writeToFile(triples: List[Tuple[str, str, str]], verbose: bool = False) -> None:
    """
    This function accepts relations as triples and writes those triples to a file.
    Args:
        triples: The triples to write to Neo4j
        verbose: True indicates verbose output should be shown.
    Returns:
        A boolean of whether the operation was successful
    """

    with open(outputFile, 'w') as f:
        for t in triples:
            f.write('%s, %s, %s\n' % (t))

def main():
    
    # Raw first few lines of Hamlet
    # playText = [["(stage directions)", "Enter two Sentinels-[first,] Francisco, [who paces up and down at his post; then] Bernardo, [who approaches him]."], ["Bernardo", "Who's there?"], ["Francisco", "Nay, answer me. Stand and unfold yourself."], ["Bernardo", "Long live the King!"], ["Francisco", "Bernardo?"], ["Bernardo", "He."], ["Francisco", "You come most carefully upon your hour."], ["Bernardo", "'Tis now struck twelve. Get thee to bed, Francisco."], ["Francisco", "For this relief much thanks. 'Tis bitter cold, And I am sick at heart."], ["Bernardo", "Have you had quiet guard?"], ["Francisco", "Not a mouse stirring."], ["Bernardo", "Well, good night. If you do meet Horatio and Marcellus, The rivals of my watch, bid them make haste."], ["(stage directions)", " Enter Horatio and Marcellus. "], ["Francisco", "I think I hear them. Stand, ho! Who is there?"], ["Horatio", "Friends to this ground."], ["Marcellus", "And liegemen to the Dane."], ["Francisco", "Give you good night."], ["Marcellus", "O, farewell, honest soldier. Who hath reliev'd you?"], ["Francisco", "Bernardo hath my place. Give you good night. Exit."], ["Marcellus", "Holla, Bernardo!"], ["Bernardo", "Say- What, is Horatio there ?"], ["Horatio", "A piece of him."], ["Bernardo", "Welcome, Horatio. Welcome, good Marcellus."], ["Marcellus", "What, has this thing appear'd again to-night?"], ["Bernardo", "I have seen nothing."], ["Marcellus", "Horatio says 'tis but our fantasy, And will not let belief take hold of him Touching this dreaded sight, twice seen of us. Therefore I have entreated him along, With us to watch the minutes of this night, That, if again this apparition come, He may approve our eyes and speak to it."], ["Horatio", "Tush, tush, 'twill not appear."], ["Bernardo", "Sit down awhile, And let us once again assail your ears, That are so fortified against our story, What we two nights have seen."], ["Horatio", "Well, sit we down, And let us hear Bernardo speak of this."]]
    # Plot overview in modern english
    # playText = [('line', 'On a dark winter night, a ghost walks the ramparts of Elsinore Castle in Denmark.'), ('line', 'Discovered first by a pair of watchmen, then by the scholar Horatio, the ghost resembles the recently deceased King Hamlet, whose brother Claudius has inherited the throne and married the king’s widow, Queen Gertrude.'), ('line', 'When Horatio and the watchmen bring Prince Hamlet, the son of Gertrude and the dead king, to see the ghost, it speaks to him, declaring ominously that it is indeed his father’s spirit, and that he was murdered by none other than Claudius.'), ('line', 'Ordering Hamlet to seek revenge on the man who usurped his throne and married his wife, the ghost disappears with the dawn.'), ('line', 'Prince Hamlet devotes himself to avenging his father’s death, but, because he is contemplative and thoughtful by nature, he delays, entering into a deep melancholy and even apparent madness.'), ('line', 'Claudius and Gertrude worry about the prince’s erratic behavior and attempt to discover its cause.'), ('line', 'They employ a pair of Hamlet’s friends, Rosencrantz and Guildenstern, to watch him.'), ('line', 'When Polonius, the pompous Lord Chamberlain, suggests that Hamlet may be mad with love for his daughter, Ophelia, Claudius agrees to spy on Hamlet in conversation with the girl.'), ('line', 'But though Hamlet certainly seems mad, he does not seem to love Ophelia: he orders her to enter a nunnery and declares that he wishes to ban marriages'), ('line', 'A group of traveling actors comes to Elsinore, and Hamlet seizes upon an idea to test his uncle’s guilt.'), ('line', 'He will have the players perform a scene closely resembling the sequence by which Hamlet imagines his uncle to have murdered his father, so that if Claudius is guilty, he will surely react.'), ('line', 'When the moment of the murder arrives in the theater, Claudius leaps up and leaves the room.'), ('line', 'Hamlet and Horatio agree that this proves his guilt.'), ('line', 'Hamlet goes to kill Claudius but finds him praying.'), ('line', 'Since he believes that killing Claudius while in prayer would send Claudius’s soul to heaven, Hamlet considers that it would be an inadequate revenge and decides to wait.'), ('line', 'Claudius, now frightened of Hamlet’s madness and fearing for his own safety, orders that Hamlet be sent to England at once.'), ('line', 'Hamlet goes to confront his mother, in whose bedchamber Polonius has hidden behind a tapestry.'), ('line', 'Hearing a noise from behind the tapestry, Hamlet believes the king is hiding there.'), ('line', 'He draws his sword and stabs through the fabric, killing Polonius.'), ('line', 'For this crime, he is immediately dispatched to England with Rosencrantz and Guildenstern.'), ('line', 'However, Claudius’s plan for Hamlet includes more than banishment, as he has given Rosencrantz and Guildenstern sealed orders for the King of England demanding that Hamlet be put to death.'), ('line', 'In the aftermath of her father’s death, Ophelia goes mad with grief and drowns in the river.'), ('line', 'Polonius’s son, Laertes, who has been staying in France, returns to Denmark in a rage.'), ('line', 'Claudius convinces him that Hamlet is to blame for his father’s and sister’s deaths.'), ('line', 'When Horatio and the king receive letters from Hamlet indicating that the prince has returned to Denmark after pirates attacked his ship en route to England, Claudius concocts a plan to use Laertes’ desire for revenge to secure Hamlet’s death.'), ('line', 'Laertes will fence with Hamlet in innocent sport, but Claudius will poison Laertes’ blade so that if he draws blood, Hamlet will die.'), ('line', 'As a backup plan, the king decides to poison a goblet, which he will give Hamlet to drink should Hamlet score the first or second hits of the match.'), ('line', 'Hamlet returns to the vicinity of Elsinore just as Ophelia’s funeral is taking place.'), ('line', 'Stricken with grief, he attacks Laertes and declares that he had in fact always loved Ophelia.'), ('line', 'Back at the castle, he tells Horatio that he believes one must be prepared to die, since death can come at any moment.'), ('line', 'A foolish courtier named Osric arrives on Claudius’s orders to arrange the fencing match between Hamlet and Laertes.'), ('line', 'The sword-fighting begins.'), ('line', 'Hamlet scores the first hit, but declines to drink from the king’s proffered goblet.'), ('line', 'Instead, Gertrude takes a drink from it and is swiftly killed by the poison.'), ('line', 'Laertes succeeds in wounding Hamlet, though Hamlet does not die of the poison immediately.'), ('line', 'First, Laertes is cut by his own sword’s blade, and, after revealing to Hamlet that Claudius is responsible for the queen’s death, he dies from the blade’s poison.'), ('line', 'Hamlet then stabs Claudius through with the poisoned sword and forces him to drink down the rest of the poisoned wine.'), ('line', 'Claudius dies, and Hamlet dies immediately after achieving his revenge.'), ('line', 'At this moment, a Norwegian prince named Fortinbras, who has led an army to Denmark and attacked Poland earlier in the play, enters with ambassadors from England, who report that Rosencrantz and Guildenstern are dead.'), ('line', 'Fortinbras is stunned by the gruesome sight of the entire royal family lying sprawled on the floor dead.'), ('line', 'He moves to take power of the kingdom.'), ('line', 'Horatio, fulfilling Hamlet’s last request, tells him Hamlet’s tragic story.'), ('line', 'Fortinbras orders that Hamlet be carried away in a manner befitting a fallen soldier.')]
    # Load playText list from a file
    # playText = eval(open('hamlet-modern.txt', 'r').read())
    # Dummy sample text
    # playText = [("line one", "John ate a sandwich. He is full. Sally ate soup. He is not hungry. She is hungry."), ("line two", "The music is too loud for it to be enjoyed. If they are angry about it, the neighbors will call the cops.")]
    # Retrieve play text from postgres
    playText = retrievePlayText()
    print('Retrieved text')
    playText = substitutePronouns(playText, verbose=False)
    print('Substituted pronouns')
    playText = coreferenceResolve(playText, verbose=False)
    print('Coreferences resolved')
    playText = spacy(playText, verbose=False)
    print('Dependencies parsed')
    relations = extractRelationships(playText, verbose=False)
    print('Relationships extracted')
    relations = postProcess(relations, verbose=False)
    print('Triples post processed')
    writeToDB(relations, verbose=False)
    print('Relations written to DB')
    writeToFile(relations, verbose=False)
    print('Relations written to file')
    return

main()
