from typing import Tuple, List
from stanfordcorenlp import StanfordCoreNLP
import json
import functools

nlp = StanfordCoreNLP('http://ec2-54-91-72-43.compute-1.amazonaws.com', port=9000)

def retrieveText(playName: str) -> List[Tuple[str, str]]:
    return [('name', 'speech')] # For now, return tuple of speaker name to their text

def preprocessText(playText: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return playText

def substitutePronouns(playText: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return playText

def coreferenceResolve(playText: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return playText

def spacy(playText: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return playText

def extractRelationships(playText: List[Tuple[str, str]], verbose: bool = False) -> List[Tuple[str, str, str]]:
    """
    Makes API calls to coreNLP using the openIE annotator to extract relationships from the play text.

    Args:
        playText: The text of a play to extract relationships from.
    Returns:
        This function returns a list of triples, where each triple represents a relationship extracted by openIE
    """

    global nlp
    properties = {'annotators': 'openie', 'outputFormat': 'json'}
    # Extract just the play text
    inputText = functools.reduce(lambda a, b: a + ' ' + b, [l[1] for l in playText])
    if verbose:
        print('Sending input text to coreNLP: %s' % inputText)

    annotations = json.loads(nlp.annotate(inputText, properties))
    if verbose:
        print('Received annotations from coreNLP: %s' % annotations)

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
    print("hello world")
    return

main()
