import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from analysis import parse_csv, parse_rules, evaluate, parse_config_csv, confirmed_c1ul_rules

ROOT = Path(__file__).parent
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/', '/index.html'):
            self.send_error(404); return
        content = (ROOT/'index.html').read_bytes()
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(content)
    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size > 30_000_000:
                raise ValueError('单次请求不能超过 30 MB，请分批导入')
            body = json.loads(self.rfile.read(size))
            if self.path == '/parse':
                import base64
                records, rules, errors, configurations = [], [], [], []
                for f in body['files']:
                    data = base64.b64decode(f['data'], validate=True)
                    try:
                        if f['name'].lower().endswith('.csv'):
                            if f['name'].lower().endswith('.zone.c.csv'):
                                r,e,c = parse_config_csv(data, f['name'])
                                if f['name'] == '2026-10-27_09.zone.C.csv':
                                    rules.extend(confirmed_c1ul_rules(c))
                                    c['warning'] = '用户确认：Max / RoC 限值顺序；本版适用于 11 月 3 日。有效公差已导入。'
                                configurations.append(c)
                            else:
                                r,e = parse_csv(data, f['name'])
                            records.extend(r); errors.extend(e)
                        else:
                            rules.extend(parse_rules(data, f['name']))
                    except Exception as e:
                        errors.append(f"{f['name']}：{e}")
                result = dict(records=records, rules=rules, errors=errors, configurations=configurations)
            elif self.path == '/analyze':
                result = evaluate(body['records'], body['rules'])
            else:
                self.send_error(404); return
            payload = json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(200)
        except Exception as e:
            payload = json.dumps({'error':str(e)},ensure_ascii=False).encode(); self.send_response(400)
        self.send_header('Content-Type', 'application/json; charset=utf-8'); self.end_headers(); self.wfile.write(payload)
if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); args=parser.parse_args()
    print(f'ISRA Analysis listening on port {args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port), Handler).serve_forever()
