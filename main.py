from typing import Tuple, List

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

def extractRelationships(playText: List[Tuple[str, str]]) -> List[Tuple[str, str, str]]:
    return playText

def postProcess(triples: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    return triples

def writeToDB(triples: List[Tuple[str, str, str]]) -> None:
    return

def main():
    print("hello world")
    return

main()
