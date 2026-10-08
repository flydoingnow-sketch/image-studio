import importlib.util
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('camera',Path(__file__).resolve().parents[1]/'server.py')
s=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(s)
class IntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory()
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),s.Router)
  cls.port=cls.server.server_port
  s.load_studios(cls.temp.name,cls.port)
  for key,name in (('hasu','哈苏'),('sony','索尼相机'),('nikon','尼康相机')):
   record={'id':key,'name':name,'icon':key[0].upper()}
   s.load_workspace(key,record)
   with __import__('sqlite3').connect(s.SHARED_DB) as c:
    c.execute('INSERT INTO workspaces(id,value) VALUES(?,?)',(key,json.dumps(record)))
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
 def setUp(self):
  s.set_shared_key('')
 def request(self,path,body=None,origin=None):
  c=HTTPConnection('127.0.0.1',self.port)
  headers={'X-Hasu-Client':'studio','Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
  r=c.getresponse();status=r.status;data=r.read();c.close();return status,data
 def test_fresh_install_has_no_workspaces(self):
  spec=importlib.util.spec_from_file_location('fresh_camera',Path(__file__).resolve().parents[1]/'server.py')
  fresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(fresh)
  with tempfile.TemporaryDirectory() as data:
   fresh.load_studios(data,self.port)
   self.assertEqual(fresh.workspace_list(),[])
   self.assertEqual(fresh.shared_key(),'')
 def test_brand_settings_and_drafts_isolated(self):
  self.assertEqual(self.request('/b/nikon/api/settings',{'brand':'尼康测试','api_key':'test-secret'})[0],200)
  self.request('/b/nikon/api/draft',{'copies':{'douyin':{'title':'尼康草稿','body':'测试'}},'platforms':['douyin']})
  nikon=json.loads(self.request('/b/nikon/api/state')[1]);sony=json.loads(self.request('/b/sony/api/state')[1])
  self.assertTrue(nikon['settings']['has_key']);self.assertNotIn('api_key',nikon['settings'])
  self.assertTrue(sony['settings']['has_key']);self.assertIsNone(sony['draft'])
  self.assertEqual(nikon['draft']['copies']['douyin']['title'],'尼康草稿')
 def test_pages_and_scoped_api_paths(self):
  for brand in s.BRANDS:
   status,html=self.request('/b/'+brand+'/');self.assertEqual(status,200)
   self.assertIn(b'id="brand-options"',html)
   self.assertIn(('/b/'+brand+'/app.js').encode(),html)
   code=self.request('/b/'+brand+'/app.js')[1].decode()
   self.assertIn("fetch(studioBase+'/api/'",code)
   self.assertIn("xhr.open('POST',studioBase+'/api/upload",code)
 def test_origin_and_unknown_brand_rejected(self):
  self.assertEqual(self.request('/b/hasu/api/draft',{},'https://evil.example')[0],403)
  self.assertEqual(self.request('/b/unknown/api/state')[0],404)
 def test_media_scope_and_range(self):
  name='a'*32+'.jpg'
  (s.STUDIOS['hasu'].DATA/'media'/name).write_bytes(b'abcdef')
  s.STUDIOS['hasu'].put('assets','asset',{'id':'asset','url':'/media/'+name})
  data=json.loads(self.request('/b/hasu/api/state')[1])
  self.assertEqual(data['assets'][0]['url'],'/b/hasu/media/'+name)
  self.assertEqual(self.request('/b/sony/media/'+name)[0],404)
  c=HTTPConnection('127.0.0.1',self.port);c.request('GET','/b/hasu/media/'+name,headers={'Range':'bytes=1-3'})
  r=c.getresponse();self.assertEqual(r.status,206);self.assertEqual(r.read(),b'bcd');c.close()
 def test_shared_key_updates_clear_and_blank_preserves(self):
  self.request('/b/hasu/api/settings',{'api_key':'shared-first'})
  for module in s.STUDIOS.values():self.assertEqual(module.settings()['api_key'],'shared-first')
  self.request('/b/sony/api/settings',{'api_key':'','tone':'索尼自己的语气'})
  self.assertEqual(s.shared_key(),'shared-first')
  self.assertNotEqual(s.STUDIOS['sony'].settings()['tone'],s.STUDIOS['hasu'].settings()['tone'])
  self.request('/b/nikon/api/settings',{'api_key':'shared-second'})
  for module in s.STUDIOS.values():self.assertEqual(module.settings()['api_key'],'shared-second')
  self.request('/b/sony/api/settings',{'clear_key':True})
  for brand in s.BRANDS:self.assertFalse(json.loads(self.request('/b/'+brand+'/api/state')[1])['settings']['has_key'])
 def test_shared_key_survives_reload_and_never_returns(self):
  self.request('/b/hasu/api/settings',{'api_key':'persisted-secret'})
  s.initialize_shared_key(s.SHARED_DB)
  self.assertEqual(s.shared_key(),'persisted-secret')
  for brand in s.BRANDS:
   self.assertNotIn(b'persisted-secret',self.request('/b/'+brand+'/api/state')[1])
 def test_invalid_settings_cannot_replace_shared_key(self):
  s.set_shared_key('keep-existing')
  status,_=self.request('/b/nikon/api/settings',{'api_key':'bad-replacement','base_url':'http://example.com'})
  self.assertEqual(status,400);self.assertEqual(s.shared_key(),'keep-existing')
 def test_custom_workspace_creation_and_restart(self):
  count=len(s.BRANDS)
  status,body=self.request('/api/workspaces',{'name':'旅行记录','icon':'T','content_direction':'旅行摄影与城市街拍','tone':'自然真实'})
  self.assertEqual(status,201);workspace=json.loads(body);key=workspace['id']
  self.assertEqual(len(s.BRANDS),count+1)
  state=json.loads(self.request('/b/'+key+'/api/state')[1])
  self.assertEqual(state['settings']['brand'],'旅行记录')
  self.assertEqual(state['settings']['content_direction'],'旅行摄影与城市街拍')
  self.assertTrue(all(a['status']=='disconnected' for a in state['accounts']))
  self.assertEqual(state['assets'],[]);self.assertIsNone(state['draft'])
  record=json.loads(__import__('sqlite3').connect(s.SHARED_DB).execute('select value from workspaces where id=?',(key,)).fetchone()[0])
  module=s.load_workspace(key,record)
  self.assertEqual(module.settings()['content_direction'],'旅行摄影与城市街拍')
  self.assertIn('新增工作区'.encode(),self.request('/b/'+key+'/')[1])
 def test_invalid_workspace_is_rejected(self):
  count=len(s.BRANDS)
  for values in ({'name':''},{'name':'x'*41},{'name':'正常','icon':'<>'}):
   self.assertEqual(self.request('/api/workspaces',values)[0],400)
  self.assertEqual(len(s.BRANDS),count)
  self.assertEqual(self.request('/api/workspaces',{'name':'跨站'},'https://evil.example')[0],403)
 def test_stop_rejects_active_task(self):
  module=s.STUDIOS['hasu']
  module.put('jobs','busy-test',{'id':'busy-test','results':{'douyin':{'status':'running'}}})
  try:self.assertEqual(self.request('/api/shutdown',{})[0],409)
  finally:
   with module.db() as c:c.execute("delete from documents where kind='jobs' and id='busy-test'")
if __name__=='__main__':unittest.main()
