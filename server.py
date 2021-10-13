from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests_async as requests
import os
from random import choice
import base64


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def parsePath():
    dirs = path.split('/')
    return dirs

def createPath(path):
    root = 'cache'
    full_path = os.path.join(root,'/'.join(path.split('/')[0:-1]))
    if not os.path.isfile(full_path):
        os.makedirs(full_path,exist_ok=True)
       
def writeToCache(path,bytes_data):
    createPath(path)
    root = 'cache'
    path = os.path.join(root,path)
    if not os.path.isfile(path):
        open(path,'wb').write(bytes_data)

def readSizeCache(path):
    root = 'cache'
    return os.stat(os.path.join(root,path)).st_size

def parseContentRange(header_data):
    byte_range = header_data.split("/")[0].split("-")
    start = int(byte_range[0].strip().replace('bytes ',''))
    end = int(byte_range[1].strip())
    return start, end
    
def readFromCache(path,start,end):
    root = 'cache'
    f = open(os.path.join(root,path),'rb')
    f.seek(start)
    data = f.read(end-start)
    return data

def getProxies():
    response = requests.get("https://actproxy.com/proxy-api/01808179c14f0ae3a22778c483f1aae9_12957-30342?format=json&userpass=true")
    list_proxies = response.json()
    return(choice(list_proxies).split(";"))

async def httpxProxy(path,headers):
    url = f"http://s3.eu-central-1.wasabisys.com/eu.minhpg.com/{path}"
    proxy = await requests.get(url)
    return proxy

async def httpxM3u8Proxy(path,headers):
    url = decodeBase64(path)
    proxy = await requests.get(url)
    return proxy


def responseReadCache(response,headers,path):
    if 'content-range' in headers:
        start, end = parseContentRange(headers['content-range'])
        size = readSizeCache(path)
        response.body = readFromCache(path,start,end)
        response.status_code = 206
    else:
        start = 0
        end = readSizeCache(path)
        size = end
        response.body = readFromCache(path,0,end)
        response.status_code = 200

    headers = {
        'Access-Control-Allow-Origin' : '*',
        'content-type' : 'binary/octet-stream',         
        'content-range' : 'bytes {}-{}/{}'.format(str(start),str(end),str(size)),
        'cache' : 'HIT',
        'server' : 'minhpg.com'
    }
    for i in headers.keys():
        response.headers[i] = headers[i]
    return response

def handleErrorProxy(proxy,response):
    response.body = proxy.content
    headers = {
        'Access-Control-Allow-Origin' : '*',
        'cache' : 'ERROR',
        'server' : 'minhpg.com'
    }
    for i in headers.keys():
        response.headers[i] = headers[i]
    response.status_code = proxy.status_code
    return response

def extractBaseUrl(url):
    components = url.split('/')
    for i in components:
        if 'm3u8' in i:
            components.pop(components.index(i))
    return '/'.join(components)

def m3u8Parser(content,baseurl):
    new_playlist = []
    lines = content.split('\n')
    for i in lines:
        if 'm3u8' in i:
            new_playlist.append('/proxy/'+generateBase64(i))
        elif 'ts' in i:
            if 'http' in i:
                new_playlist.append('/proxy/'+generateBase64(i))
            else:
                new_playlist.append('/proxy/'+generateBase64(baseurl+'/'+i))
        else:
            new_playlist.append(i)
    return '\n'.join(new_playlist)

async def proxy(request,response,path):
    headers = request.headers
    root='cache'
    if not os.path.isfile(os.path.join(root,path)):
        proxy = await httpxProxy(path,dict(headers))
        if proxy.status_code == 200:
            writeToCache(path,proxy.content)
            response = responseReadCache(response,headers,path)
        else:
            response = handleErrorProxy(proxy,response)
    else:
        response = responseReadCache(response,headers,path)
    return response

async def proxy_m3u8(request,response,path):
    url = path
    path = generateBase64(path)
    headers = request.headers
    root='cache'
    if not os.path.isfile(os.path.join(root,path)):
        proxy = await httpxM3u8Proxy(path,dict(headers))
        if proxy.status_code == 200:
            if 'm3u8' in url:
                baseurl = extractBaseUrl(url)
                data = m3u8Parser(proxy.text,baseurl)
                response.body = bytes(data,"UTF-8")
                response.status_code = 200
                headers = {
                    'Access-Control-Allow-Origin' : '*',
                    'content-type' : 'application/vnd.apple.mpegurl',         
                    'cache' : 'MISS',
                    'server' : 'minhpg.com'
                }
                for i in headers.keys():
                    response.headers[i] = headers[i]                
            else:
                writeToCache(path,proxy.content)
                response = responseReadCache(response,headers,path)
        else:
            response = handleErrorProxy(proxy,response)
    else:
        response = responseReadCache(response,headers,path)
    return response

@app.get("/player/{path:path}", response_class=HTMLResponse)
async def player(request: Request, path: str):
    return templates.TemplateResponse("gapo.html", {"request": request, "hd": '/proxy/'+generateBase64(path),"type":'m3u8'})


@app.get("/proxy/{path:path}")
async def _proxy_playlist(path: str, response: Response, request: Request):
    try:
        path = decodeBase64(path)
        response = await proxy_m3u8(request,response,path)
    except Exception as exception:
        response.headers['server'] = 'minhpg.com'
        return {'error':str(exception)}
    return response

@app.get("/{path:path}")
async def _proxy(path: str, response: Response, request: Request):
    try:
        response = await proxy(request,response,path)
    except Exception as exception:
        response.headers['server'] = 'minhpg.com'
        return {'error':str(exception)}
    return response


def generateBase64(string):
    return base64.b64encode(bytes(string, 'utf-8')).decode("utf-8")

def decodeBase64(string):
    return base64.b64decode(bytes(string, 'utf-8')).decode("utf-8")