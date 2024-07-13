from flask import Flask, request, Response, redirect, url_for
import requests
from bs4 import BeautifulSoup
import re
import json

app = Flask(__name__, static_folder=None)

WIKIPEDIA_URL = "https://en.wikipedia.org"


l = []

@app.route('/log')
def log():
    s = ''

    for i in l:
        s += f'<p>{i}</p>'

    return s

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    if 'wiki' in path or request.args.get('search') is not None:
        l.append(path + ' ' + str(request.args.get('search')))

    url = f"{WIKIPEDIA_URL}/{path}"
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}

    if request.method == 'POST':
        response = requests.post(url, headers=headers, data=request.form)
    else:
        response = requests.get(url, headers=headers, params=request.args)

    if response.status_code == 302:
        location = response.headers['location'].replace(WIKIPEDIA_URL, request.host_url)
        return redirect(location, code=302)

    content = response.content
    content_type = response.headers.get('content-type', '')

    if 'text/html' in content_type:
        content = modify_html(content)
    # elif 'application/json' in content_type:
    #     content = modify_json(content)

    headers = dict(response.headers)
    headers.pop('content-encoding', None)
    headers.pop('transfer-encoding', None)
    headers.pop('content-length', None)

    return Response(content, status=response.status_code, headers=headers)


def modify_html(content):
    soup = BeautifulSoup(content, 'html.parser')

    # Update relative URLs to absolute URLs
    for tag in soup.find_all(['a', 'link', 'script', 'img']):
        for attr in ['href', 'src']:
            if tag.has_attr(attr):
                url = tag[attr]
                if url.startswith('//'):
                    tag[attr] = f"https:{url}"
                elif url.startswith('/'):
                    tag[attr] = f"{request.host_url[:-1]}{url}"
                elif url.startswith('./'):
                    tag[attr] = f"{request.host_url}{url[2:]}"

    # Fix inline styles with url() functions
    for tag in soup.find_all(style=True):
        tag['style'] = re.sub(r'url\(["\']?(/[^)"\']+)["\']?\)', rf'url({request.host_url[:-1]}\1)', tag['style'])

    # Modify JavaScript to use the proxy URL
    for script in soup.find_all('script'):
        if script.string:
            script.string = script.string.replace(WIKIPEDIA_URL, request.host_url[:-1])

    return str(soup)


def modify_json(content):
    data = json.loads(content)
    if isinstance(data, dict) and 'query' in data:
        for page in data['query'].get('pages', {}).values():
            if 'thumbnail' in page:
                page['thumbnail']['source'] = page['thumbnail']['source'].replace(WIKIPEDIA_URL, request.host_url[:-1])
    return json.dumps(data)


if __name__ == '__main__':
    app.run(debug=True)