import requests
from bs4 import BeautifulSoup

def getTable(data):
    for i in data:
        if '<tbody>' in i:
            init = data.index(i)
        if '</tbody>' in i:
            end = data.index(i)
    return data[init+1:end]

def parseTable(table):
    soup = BeautifulSoup(table,'html.parser')
    data = soup.find_all('td')
    for i in data:
        try:
            print(i.a.attrs)
            print(i.img.attrs)
        except:
            
            print(i.text)


def fetchStream():
    response = requests.get("http://nba-streams.xyz/")
    data = response.text.split('\n')
    table = '\n'.join(getTable(data))
    data = parseTable(table)

def hello():
    fetchStream()

hello()