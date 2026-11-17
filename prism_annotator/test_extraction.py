import unittest
from unittest.mock import patch,Mock
from extraction import Gemini,choose_backend
from app import Batch
class ProviderTests(unittest.TestCase):
 def test_manual(self):
  with patch('builtins.input',return_value='3'):self.assertIsNone(choose_backend())
 def test_offline(self):
  with patch('builtins.input',return_value='1'),patch('extraction.Ollama') as factory,patch('extraction.select_model',return_value={'name':'local','digest':'abc'}):
   c,m=choose_backend();self.assertIs(c,factory.return_value);self.assertEqual(m['provider'],'ollama')
 def test_online(self):
  with patch('builtins.input',side_effect=['2','model']),patch('extraction.getpass.getpass',return_value='secret'),patch('extraction.Gemini') as factory:
   factory.return_value.options={'temperature':0};c,m=choose_backend();self.assertEqual(m['provider'],'gemini');self.assertNotIn('secret',str(m))
 def test_schema_shared(self):
  c=Gemini.__new__(Gemini);c.client=Mock();c.client.models.generate_content.return_value=Mock(text='{"kos":[]}',candidates=[])
  result=c.extract('m','prompt',{'raw_text':'policy'},Batch.model_json_schema());self.assertEqual(Batch.model_validate_json(result).kos,[])
  self.assertEqual(c.client.models.generate_content.call_args.kwargs['config']['response_json_schema'],Batch.model_json_schema())
 def test_error_redaction(self):
  c=Gemini.__new__(Gemini);c.client=Mock();c.client.models.generate_content.side_effect=ValueError('secret key')
  with self.assertRaises(RuntimeError) as error:c.extract('m','p',{}, {})
  self.assertNotIn('secret key',str(error.exception))
if __name__=='__main__':unittest.main()
