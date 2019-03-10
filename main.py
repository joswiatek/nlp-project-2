from typing import Tuple, List
from stanfordcorenlp import StanfordCoreNLP
import json
import functools
import spacy
from spacy.symbols import PRON


nlp = StanfordCoreNLP('http://ec2-54-91-72-43.compute-1.amazonaws.com', port=9000)
parser = spacy.load('en_core_web_sm')

def retrieveText(playName: str) -> List[Tuple[str, str]]:
    return [('name', 'speech')] # For now, return tuple of speaker name to their text
    
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
        currchar = character
        doc = parser(dialogue)
        subs = ''
        for j, word in enumerate(doc):
            if word.pos == PRON and word.lower_ in ['i', 'me']:
                if verbose:
                    print(f'substituting {word.text} to {character.capitalize()}')
                subs += word.text_with_ws.replace(word.text, character.capitalize())
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
    global nlp
    properties = {'annotators': 'coref', 'outputFormat': 'json'}
    for i, (character, dialogue) in enumerate(playText):
        inputText = dialogue
        if verbose:
            print('Sending original input text to coreNLP: %s' % inputText)

        annotations = json.loads(nlp.annotate(inputText, properties))

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
            original = functools.reduce(lambda a, b: a + ' ' + b, filter(lambda v: v != ' ', s[:-1]))
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

    global nlp
    properties = {'annotators': 'openie', 'outputFormat': 'json'}
    # Extract just the play text
    inputText = functools.reduce(lambda a, b: a + ' ' + b, [l[1] for l in playText])
    if verbose:
        print('Sending input text to coreNLP: %s\n' % inputText)

    annotations = json.loads(nlp.annotate(inputText, properties))

    # Unwrapped list comprehension is shown below
    relations = [(result['subject'], result['relation'], result['object']) for sentence in annotations['sentences'] for result in sentence['openie']]
    """
    for sentence in annotations['sentences']:
        for result in sentence['openie']:
            relation = (result['subject'], result['relation'], result['object'])
            relations.append(relation)
    """
    return relations

def postProcess(triples: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    return triples

def writeToDB(triples: List[Tuple[str, str, str]]) -> None:
    return

def main():
    playText = [["(stage directions)", "Enter two Sentinels-[first,] Francisco, [who paces up and down at his post; then] Bernardo, [who approaches him]."], ["Bernardo", "Who's there?"], ["Francisco", "Nay, answer me. Stand and unfold yourself."], ["Bernardo", "Long live the King!"], ["Francisco", "Bernardo?"], ["Bernardo", "He."], ["Francisco", "You come most carefully upon your hour."], ["Bernardo", "'Tis now struck twelve. Get thee to bed, Francisco."], ["Francisco", "For this relief much thanks. 'Tis bitter cold, And I am sick at heart."], ["Bernardo", "Have you had quiet guard?"], ["Francisco", "Not a mouse stirring."], ["Bernardo", "Well, good night. If you do meet Horatio and Marcellus, The rivals of my watch, bid them make haste."], ["(stage directions)", " Enter Horatio and Marcellus. "], ["Francisco", "I think I hear them. Stand, ho! Who is there?"], ["Horatio", "Friends to this ground."], ["Marcellus", "And liegemen to the Dane."], ["Francisco", "Give you good night."], ["Marcellus", "O, farewell, honest soldier. Who hath reliev'd you?"], ["Francisco", "Bernardo hath my place. Give you good night. Exit."], ["Marcellus", "Holla, Bernardo!"], ["Bernardo", "Say- What, is Horatio there ?"], ["Horatio", "A piece of him."], ["Bernardo", "Welcome, Horatio. Welcome, good Marcellus."], ["Marcellus", "What, has this thing appear'd again to-night?"], ["Bernardo", "I have seen nothing."], ["Marcellus", "Horatio says 'tis but our fantasy, And will not let belief take hold of him Touching this dreaded sight, twice seen of us. Therefore I have entreated him along, With us to watch the minutes of this night, That, if again this apparition come, He may approve our eyes and speak to it."], ["Horatio", "Tush, tush, 'twill not appear."], ["Bernardo", "Sit down awhile, And let us once again assail your ears, That are so fortified against our story, What we two nights have seen."], ["Horatio", "Well, sit we down, And let us hear Bernardo speak of this."]]
    #playText = [("line one", "John ate a sandwich. He is full. Sally ate soup. He is not hungry. She is hungry."), ("line two", "The music is too loud for it to be enjoyed. If they are angry about it, the neighbors will call the cops.")]
    playText = substitutePronouns(playText, verbose=False)
    playText = coreferenceResolve(playText, verbose=False)
    playText = spacy(playText, verbose=False)
    relations = extractRelationships(playText, verbose=False)
    print(relations)
    return

main()
