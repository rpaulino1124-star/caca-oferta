import unittest
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from worker import score, validate_product, allowed_url, issue_product, make_video

class TestOfertiva(unittest.TestCase):
    def test_reject_external_link(self):
        with self.assertRaises(ValueError):
            validate_product({"name": "Produto", "affiliate_url": "https://example.com",
                              "images": ["https://cdn.shopee.com.br/a.jpg"]})

    def test_score_ranking(self):
        good = {"rating": 4.9, "sales": 500, "commission_pct": 12, "price": 70}
        weak = {"rating": 2.5, "sales": 5, "commission_pct": 2, "price": 10}
        self.assertGreater(score(good), score(weak))

    def test_reject_http_images(self):
        self.assertFalse(allowed_url("http://img.susercontent.com/test.png", ("susercontent.com",)))

    def test_no_fake_affiliate_link(self):
        self.assertFalse(allowed_url("https://shopee.com.br.evil.example/item", ("shopee.com.br",)))


    def test_issue_payload(self):
        p = {"name":"Teste legítimo", "affiliate_url":"https://shopee.com.br/item",
             "images":["https://down-br.img.susercontent.com/file/teste"],"price":45}
        tick = chr(96)*3
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"event.json"
            path.write_text(json.dumps({"issue":{"body":tick+"ofertiva\n"+json.dumps(p)+"\n"+tick}}))
            with patch.dict(os.environ,{"GITHUB_EVENT_PATH":str(path)}):
                self.assertEqual(issue_product()["name"],"Teste legítimo")

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg não instalado")
    def test_video_from_synthetic_image(self):
        p = validate_product({"name":"Produto de teste sem publicidade",
              "affiliate_url":"https://shopee.com.br/teste",
              "images":["https://down-br.img.susercontent.com/file/teste"],"price":50})
        with patch("worker.download_image",return_value=Image.new("RGB",(400,400),"orange")):
            with patch.dict(sys.modules, {"edge_tts": None}):
                video = make_video(p,"Texto de teste")
        self.assertTrue(video.exists())
        self.assertGreater(video.stat().st_size,2000)

if __name__ == "__main__":
    unittest.main()
