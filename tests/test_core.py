import importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
SPEC=importlib.util.spec_from_file_location('studio',Path(__file__).resolve().parents[1]/'core/server.py')
s=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(s)
class StudioTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();s.DATA=Path(self.temp.name);s.init()
  s.put('assets','video',{'id':'video','kind':'video','filename':'video.mp4'})
  s.put('assets','cover',{'id':'cover','kind':'image','filename':'cover.jpg'})
  self.payload={'video_id':'video','cover_id':'cover','platforms':['xiaohongshu','tencent','douyin'],'tags':['摄影'],'copies':{p:{'title':'真实标题','body':'真实正文'} for p in s.PLATFORMS}}
 def tearDown(self): self.temp.cleanup()
 def connect_all(self):
  for p in s.PLATFORMS:s.put('accounts',p,{'id':p,'status':'connected'})
 def test_missing_accounts_block_publish(self):
  with self.assertRaises(s.AppError):s.validate_publish(self.payload)
 def test_title_and_tag_limits(self):
  self.connect_all();self.payload['copies']['xiaohongshu']['title']='字'*21
  with self.assertRaises(s.AppError):s.validate_publish(self.payload)
  with self.assertRaises(s.AppError):s.normalize_tags(list(map(str,range(11))))
 def test_duplicate_platforms_rejected(self):
  self.connect_all();self.payload['platforms']=['douyin','douyin']
  with self.assertRaises(s.AppError):s.validate_publish(self.payload)
 def test_secret_is_never_returned(self):
  s.put('settings','main',{'api_key':'test-secret'})
  self.assertNotIn('api_key',s.public_settings());self.assertTrue(s.public_settings()['has_key'])
 def test_generation_requires_real_service(self):
  with self.assertRaises(s.AppError):s.require_ai(s.settings())
 def test_duplicate_submission_returns_same_job(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):
   a=s.create_publish(self.payload);b=s.create_publish(self.payload)
  self.assertEqual(a['id'],b['id']);self.assertEqual(len(s.all_docs('jobs')),1)
 def test_submitted_job_cannot_retry(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  s.update_result(j['id'],'douyin',status='submitted')
  with self.assertRaises(s.AppError):s.retry_job(j['id'],'douyin',True)
 def test_uncertain_requires_explicit_review(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  s.update_result(j['id'],'douyin',status='uncertain')
  with self.assertRaises(s.AppError):s.retry_job(j['id'],'douyin')
 def test_precheck_failure_stops_before_upload(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  with patch.object(s,'run_cli',return_value=(1,'invalid')) as cli:s.publish_worker(j['id'],['douyin'])
  self.assertEqual(cli.call_count,1);self.assertEqual(s.get('jobs',j['id'])['results']['douyin']['status'],'failed')
 def test_zero_exit_without_success_is_uncertain(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  with patch.object(s,'run_cli',side_effect=[(0,'valid\n'),(0,'operation ended')]):s.publish_worker(j['id'],['douyin'])
  self.assertEqual(s.get('jobs',j['id'])['results']['douyin']['status'],'uncertain')
 def test_success_requires_platform_evidence(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  with patch.object(s,'run_cli',side_effect=[(0,'valid\n'),(0,'视频发布成功')]):s.publish_worker(j['id'],['douyin'])
  self.assertEqual(s.get('jobs',j['id'])['results']['douyin']['status'],'submitted')
 def test_restart_marks_interrupted_jobs_uncertain(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  s.init();self.assertEqual(s.get('jobs',j['id'])['results']['douyin']['status'],'uncertain')
 def test_vision_result_validation_and_prompt_data(self):
  s.put('settings','main',{'api_key':'test-key','base_url':'https://example.test/v1','vision_model':'vision'})
  s.put('assets','video',{'id':'video','kind':'video','duration':10,'has_audio':False})
  output={'summary':'测试图形','uncertainties':['仅根据抽样画面'],'tags':['#摄影'],'copies':self.payload['copies'],'cover_prompt':'图形'}
  with patch.object(s,'frame',return_value=b'frame'),patch.object(s,'ai_call',return_value={'choices':[{'message':{'content':json.dumps(output)}}]}) as call:
   result=s.analyze({'video_id':'video'})
  self.assertEqual(result['sample_count'],4);self.assertEqual(result['tags'],['摄影'])
  self.assertEqual(len(call.call_args.args[2]['messages'][0]['content']),9)
  self.assertIn('未配置语音识别',result['notice'])
 def test_all_submitted_clears_matching_draft(self):
  self.connect_all();s.put('drafts','current',self.payload)
  s.put('settings','main',{'api_key':'preserve-test-key'})
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  for p in s.PLATFORMS:s.update_result(j['id'],p,status='submitted')
  self.assertIsNone(s.get('drafts','current'))
  self.assertEqual(s.settings()['api_key'],'preserve-test-key')
  self.assertEqual(s.account('douyin')['status'],'connected')
 def test_partial_submission_preserves_draft(self):
  self.connect_all();s.put('drafts','current',self.payload)
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  s.update_result(j['id'],'douyin',status='submitted')
  s.update_result(j['id'],'tencent',status='uncertain')
  self.assertIsNotNone(s.get('drafts','current'))
 def test_completion_preserves_newer_edits(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  changed=json.loads(json.dumps(self.payload));changed['copies']['douyin']['title']='新的草稿'
  s.put('drafts','current',changed)
  for p in s.PLATFORMS:s.update_result(j['id'],p,status='submitted')
  self.assertEqual(s.get('drafts','current'),changed)
 def test_historical_completed_draft_cleanup(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'):j=s.create_publish(self.payload)
  for p in s.PLATFORMS:s.update_result(j['id'],p,status='submitted')
  s.put('drafts','current',self.payload)
  self.assertTrue(s.clear_completed_draft())
  self.assertTrue(s.completed_draft(self.payload))
 def test_bad_model_output_is_rejected(self):
  s.put('settings','main',{'api_key':'test-key','base_url':'https://example.test/v1','vision_model':'vision'})
  s.put('assets','video',{'id':'video','kind':'video','duration':1})
  with patch.object(s,'frame',return_value=b'frame'),patch.object(s,'ai_call',return_value={'choices':[{'message':{'content':'not json'}}]}):
   with self.assertRaises(s.AppError):s.analyze({'video_id':'video'})
 def test_schedule_validation(self):
  self.assertIsNone(s.validate_schedule(None))
  for value in ['', '2020-01-01T12:00', '2030-01-01T12:00', '2026-10-09T12:30', 123]:
   with self.assertRaises(s.AppError): s.validate_schedule(value)
 def test_schedule_dispatch_and_identity(self):
  self.connect_all()
  target=(s.datetime.now(s.timezone(s.timedelta(hours=8)))+s.timedelta(days=1)).replace(minute=0).strftime('%Y-%m-%dT%H:%M')
  with patch.object(s.threading.Thread,'start'):
   immediate=s.create_publish(self.payload)
   self.payload['schedule']=target
   scheduled=s.create_publish(self.payload)
  self.assertNotEqual(immediate['id'],scheduled['id'])
  with patch.object(s,'run_cli',side_effect=[(0,'valid\n'),(0,'视频发布成功')]) as run:
   s.publish_worker(scheduled['id'],['douyin'])
  args=run.call_args_list[1].args[0]
  self.assertEqual(args[args.index('--schedule')+1],target.replace('T',' '))
 def test_expired_schedule_blocks_retry_and_dispatch(self):
  self.connect_all()
  with patch.object(s.threading.Thread,'start'): job=s.create_publish(self.payload)
  job['payload']['schedule']='2020-01-01T12:00';job['results']['douyin']['status']='failed';s.put('jobs',job['id'],job)
  with self.assertRaises(s.AppError):s.retry_job(job['id'],'douyin')
  with patch.object(s,'run_cli',return_value=(0,'valid\n')) as run:s.publish_worker(job['id'],['douyin'])
  self.assertEqual(run.call_count,1)
  self.assertEqual(s.get('jobs',job['id'])['results']['douyin']['status'],'failed')
if __name__=='__main__':unittest.main()
