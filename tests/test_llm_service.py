import unittest
import socket
import urllib.error
from unittest.mock import patch, MagicMock
from core.translation.llm_translation_service import GeminiRESTProvider

class TestLLMService(unittest.TestCase):
    def setUp(self):
        self.provider = GeminiRESTProvider(api_key="TEST", timeout=5.0)

    @patch('urllib.request.urlopen')
    def test_timeout_error_handling(self, mock_urlopen):
        # Simulate a socket.timeout
        mock_urlopen.side_effect = socket.timeout("Timed out")
        
        with self.assertRaises(RuntimeError) as context:
            self.provider.translate("Hello")
            
        self.assertIn("Network error during API call", str(context.exception))
        self.assertIn("Timed out", str(context.exception))

    @patch('urllib.request.urlopen')
    def test_http_error_handling(self, mock_urlopen):
        # Simulate a 429 HTTPError
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"error": "Too Many Requests"}'
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=mock_response
        )
        
        with self.assertRaises(RuntimeError) as context:
            self.provider.translate("Hello")
            
        self.assertIn("Gemini API Error 429", str(context.exception))
        self.assertIn("Too Many Requests", str(context.exception))
        
    @patch('urllib.request.urlopen')
    def test_url_error_handling(self, mock_urlopen):
        # Simulate a connection refused URLError
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        with self.assertRaises(RuntimeError) as context:
            self.provider.translate("Hello")
            
        self.assertIn("Network error during API call", str(context.exception))
        self.assertIn("Connection refused", str(context.exception))

if __name__ == "__main__":
    unittest.main()
