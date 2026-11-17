import unittest,json
from unittest.mock import patch
from ollama_backend import Ollama,select_model
from app import Batch
class OllamaTests(unittest.TestCase):
 def test_models_filter_cloud(self):
  c=Ollama()
  with patch.object(c,'request',return_value={'models':[{'name':'local:8b'},{'name':'test-cloud'},{'name':'alias','remote_host':'https://example.com'}]}):self.assertEqual(c.models(),[{'name':'local:8b'}])
 def test_cloud_alias_blocked(self):
  c=Ollama()
  with patch.object(c,'request',return_value={'remote_model':'remote'}):
   with self.assertRaises(RuntimeError):c.verify_local('alias')
 def test_schema_chat(self):
  c=Ollama()
  with patch.object(c,'request',return_value={'done':True,'message':{'content':'{"kos":[]}'}}) as request:
   self.assertEqual(Batch.model_validate_json(c.extract('local','prompt',{'raw_text':'hello'},Batch.model_json_schema())).kos,[])
   payload=request.call_args.args[1];self.assertFalse(payload['stream']);self.assertEqual(payload['format'],Batch.model_json_schema());self.assertNotIn('api_key',payload)
 def test_incomplete(self):
  c=Ollama()
  with patch.object(c,'request',return_value={'done':True,'done_reason':'length','message':{'content':'{}'}}):
   with self.assertRaises(RuntimeError):c.extract('local','p',{}, {})
 def test_model_selection(self):
  c=Ollama()
  with patch.object(c,'models',return_value=[{'name':'local:8b','digest':'abc'}]),patch.object(c,'verify_local') as verify,patch('builtins.input',return_value='1'):
   self.assertEqual(select_model(c)['digest'],'abc');verify.assert_called_once_with('local:8b')
if __name__=='__main__':unittest.main()
