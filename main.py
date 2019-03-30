from typing import Tuple, List
import contractions
import stanfordnlp
import json
import functools
import spacy
import os
import time
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

modernPlays = ['12night','antonycleo','asyoulikeit','hamlet','juliuscaesar','kinglear','macbeth','measure','merchantvenice','midsummer','othello','richard2','richard3','romeojuliet','tempest','winterstale']

outputFile = '-triples.txt'

def retrieveText(url: str) -> List[Tuple[str, str]]:
    response = urllib.request.urlopen(url)
    playText = eval(response.read())
    return playText

def retrievePlayCharacters(play: str) -> List[Tuple[str, str]]:
    url = urllib.parse.urljoin(postGresBaseURL, play + '/characters')
    return retrieveText(url)

def retrievePlayText(play: str) -> List[Tuple[str, str]]:
    url = urllib.parse.urljoin(postGresBaseURL + 'modern/', play)
    return retrieveText(url)

def loadRelationsFromFile(play: str) -> List[Tuple[str, str, str]]:
    relations = []
    with open('final-triples/' + play + outputFile, 'r') as f:
        for line in f:
            relation = line.split(',')
            for i in range(len(relation)):
                relation[i] = relation[i].strip()
            relations.append(tuple(relation))
    return relations

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

    return relations

def postProcess(triples: List[Tuple[str, str, str]], play: str, verbose: bool = True) -> List[Tuple[str, str, str]]:
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
    characters = retrievePlayCharacters(play)
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

def writeToDB(triples: List[Tuple[str, str, str]], playName: str, verbose: bool = False) -> None:
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
                        "MERGE (%s1:node {name: \"%s\", play:\"%s\"})" % (strToNodeName(relation[0]), relation[0], playName),
                        "MERGE (%s2:node {name: \"%s\", play:\"%s\"})" % (strToNodeName(relation[2]), relation[2], playName),
                        ]
                    # Connect the two with the relation if the relation isn't already there
                    relationStatement = "MERGE (%s1)-[:relation {action:\"%s\", play:\"%s\"}]->(%s2)" % (strToNodeName(relation[0]), relation[1], playName, strToNodeName(relation[2]))
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

def writeToFile(triples: List[Tuple[str, str, str]], fileName: str, verbose: bool = False) -> None:
    """
    This function accepts relations as triples and writes those triples to a file.
    Args:
        triples: The triples to write to Neo4j
        verbose: True indicates verbose output should be shown.
    Returns:
        A boolean of whether the operation was successful
    """

    with open(fileName, 'w') as f:
        for t in triples:
            f.write('%s, %s, %s\n' % (t))

def main():
    for play in modernPlays:
        startTime = time.time()

        print('Retrieving text for play: %s' % play)
        playText = retrievePlayText(play)
        print('Retrieved text, substituting pronouns')
        playText = substitutePronouns(playText, verbose=False)
        print('Substituted pronouns, resolving coreferences')
        playText = coreferenceResolve(playText, verbose=False)
        print('Coreferences resolved, parsing dependencies')
        playText = spacy(playText, verbose=False)
        print('Dependencies parsed, extracting relationships')
        relations = extractRelationships(playText, verbose=False)
        print('Relationships extracted, post processing triples')
        relations = postProcess(relations, play, verbose=False)
        print('Triples post processed, writing to DB')
        writeToDB(relations, play, verbose=False)
        print('Relations written to DB, writing relations to file')
        writeToFile(relations, play + outputFile, verbose=False)
        print('Relations written to file: %s' % play + outputFile)

        endTime = time.time()
        totalSeconds = endTime - startTime
        m, s = divmod(totalSeconds, 60)
        h, m = divmod(m, 60)

        print('Done with %s, full pipeline took %d hours, %02d minutes, %02d seconds' % (play, h, m, s))
    return

main()
