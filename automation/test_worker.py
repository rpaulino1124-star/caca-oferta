import unittest
from worker import score, validate_product, allowed_url

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

if __name__ == "__main__":
    unittest.main()
