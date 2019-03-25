import sys
import re
from lxml import html
import requests
import time

# SOME CODE WAS TAKEN FROM https://github.com/aforsyth/nfs-webscraper

play = sys.argv[1]
output = open('raw/' + play + '.txt', 'w')
base_url = 'https://www.sparknotes.com/nofear/shakespeare/' + play + '/'
allText = []

# For a specific play, try all possible pages. Break when 404
for i in range(2, 20000, 2):
    time.sleep(0.5)
    print('Page: ', i)
    singlePage = requests.get(base_url + 'page_' + str(i) + '/')
    singleTree = html.fromstring(singlePage.content)
    modernTds = singleTree.xpath('//td[@class="noFear-right"]')[1:] #don't include heading
    if len(modernTds) == 0:
        break
        
        
    def sanitizeText(t):
        t = str(t.encode('utf-8').decode('ascii', 'ignore'))
        t = t.replace("\n","")
        t = t.replace("\t", "")
            
        tList = t.split(" ")
            
        outputString = ""
        for word in tList:
            if len(word) > 0:
                outputString += word
                outputString += " "       
        return outputString[:-1] #removes trailingSpace
        
        #Takes in a list of the td's. Returns a list of lists, the outer list corresponds to table entires
        #The inner list corresponds to the lines in that table entry
        #The outer list should be of the same size for modern and original text
        #The inner lists are not guaranteed to be of the same size based on how NFS is structured
        def readLines(tdList):
            text = []
            for td in tdList:
                newEntry = []
                children = td.getchildren()
                for lineDiv in children:
                    lineDivValues = lineDiv.values()
                    if len(lineDivValues) > 0:   
                        divClass = lineDivValues[0]
                        #don't include stage directions
                        if divClass == "modern-stage":
                            continue
                    unsanitized = lineDiv.text_content()
                    sanitized = sanitizeText(unsanitized)
                    newEntry.append(sanitized)
                if len(newEntry) > 0:
                    text.append(newEntry)
            return text
            
        modernText = readLines(modernTds)
        allText.extend(modernText)
    

for tableEntry in allText:
    output.write("<T>\n")
    for line in tableEntry:
        output.write(line + "\n")
    output.write("</T>\n")

output.close()
    

	
