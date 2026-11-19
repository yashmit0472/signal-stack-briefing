"""Offline regression tests for transient Gemini/Tavily failures and partial discovery."""
import os
import unittest
from unittest.mock import patch, Mock
import requests
import engine


def ok_response(payload):
    response=Mock()
    response.status_code=200
    response.json.return_value=payload
    return response


class DiscoveryRecoveryTests(unittest.TestCase):
    @patch('engine.time.sleep')
    @patch('engine.requests.post')
    def test_network_timeout_retries_then_returns(self, post, sleep):
        post.side_effect=[requests.exceptions.Timeout(),ok_response({'results':[]})]
        with patch.dict(os.environ,{'TAVILY_API_KEY':'dummy'},clear=False):
            self.assertEqual(engine.search('student feedback'),[])
        self.assertEqual(post.call_count,2)
        sleep.assert_called_once()

    @patch('engine.time.sleep')
    @patch('engine.requests.post')
    def test_http_503_retries_and_reports_failure_without_leaking_key(self, post, sleep):
        unavailable=Mock(status_code=503)
        post.return_value=unavailable
        with patch.dict(os.environ,{'TAVILY_API_KEY':'private_test_key'},clear=False):
            with self.assertRaisesRegex(RuntimeError,'Tavily HTTP 503.*after 3 attempts') as caught:
                engine.search('admission dates')
        self.assertNotIn('private_test_key',str(caught.exception))
        self.assertEqual(post.call_count,3)

    @patch('engine._provider_json',return_value={'candidates':[{'content':{'parts':[{'text':'[1,2,3]'}]}}]})
    def test_unexpected_model_json_array_gives_clear_error(self, provider):
        schema={'type':'OBJECT','properties':{'sources':{'type':'ARRAY'}}}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'dummy'},clear=False):
            with self.assertRaisesRegex(ValueError,'expected a JSON object'):
                engine.model('Return an object',{},schema=schema)

    @patch('open_sources.candidates')
    @patch('engine.discover_competitors')
    @patch('engine.propose')
    @patch('engine.search')
    @patch('engine.model')
    @patch('engine.context',return_value={'name':'Example','website':'https://example.com'})
    def test_partial_discovery_saves_valid_sources_and_surfaces_errors(self, context, model, search, propose, competitors, opens):
        model.side_effect=[
            {'Customers':['customer q'],'Market':['market q'],'Competitors':[]},
            {'sources':[{'index':0,'reason':'customer problems'}]},
        ]
        def fake_search(q):
            if q=='market q':
                raise RuntimeError('upstream outage')
            return [{'url':'https://forum.example.com/123','title':'Relevant discussion','content':'A customer question about the product'}]
        search.side_effect=fake_search
        with self.assertRaisesRegex(engine.PartialDiscoveryError,'market q|Market search'):
            engine.discover('sample')
        propose.assert_called_once()
        competitors.assert_called_once()
        opens.assert_called_once()

if __name__=='__main__':
    unittest.main(verbosity=2)
