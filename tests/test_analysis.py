import unittest
from analysis import parse_csv, parse_rules, evaluate

class AnalysisTests(unittest.TestCase):
    def record(self, product='BMW', value=-85):
        data=f'2026-01-29_100034,29.01.2026,10:00:34,227,9,{product},+,A_HORIZONTAL,+,{value},1040,697,47,1054,687'
        r,e=parse_csv(data.encode(),'test.csv');self.assertEqual(e,[]);return r
    def test_mixed_products_and_boundaries(self):
        rules=[dict(product='BMW',item='A_HORIZONTAL',metric='maximum',lower=-85,upper=85)]
        out=evaluate(self.record()+self.record('C1UL'),rules)
        self.assertEqual([r['status'] for r in out],['合格','未配置','未配置','未配置'])
        self.assertEqual(evaluate(self.record(value=-86),rules)[0]['status'],'超差')
    def test_invalid_row_not_silently_accepted(self):
        r,e=parse_csv(b'Zone,Blob-Nr.,Area,Quality,max. Optic\n','empty.csv')
        self.assertEqual(r,[]);self.assertEqual(len(e),1)
    def test_nonfinite(self):
        with self.assertRaises(AssertionError): self.record(value='nan')
    def test_dfq_limits(self):
        rules=parse_rules(b'K1001 BMW\nK2002/1 A_HORIZONTAL_Max\nK2112/1 -85\nK2113/1 85\n','a.dfq')
        self.assertEqual(evaluate(self.record(),rules)[0]['status'],'合格')
    def test_conflicting_limits(self):
        a=dict(product='BMW',item='A_HORIZONTAL',metric='maximum',lower=-85,upper=85)
        with self.assertRaises(ValueError):evaluate(self.record(),[a,{**a,'upper':90}])
    def test_xml_encoding_and_ambiguous_limits(self):
        xml=b'<?xml version="1.0" encoding="utf-16"?><Report><Product_info><Program_name name="BMW"/></Product_info><Measurements><Measurement><Zone_name name="A_HORIZONTAL"/><Result_maximum_limit_A name="85"/><Result_maximum_limit_B name="85"/><ROC_limit_A name="100"/><ROC_limit_B name="100"/></Measurement></Measurements></Report>'
        self.assertEqual(len(parse_rules(xml,'a.xml')),2)
        with self.assertRaises(ValueError):parse_rules(xml.replace(b'B name="85"',b'B name="90"'),'a.xml')
if __name__=='__main__':unittest.main()

class ConfigTests(unittest.TestCase):
    def test_confirmed_c1ul(self):
        from analysis import parse_config_csv, confirmed_c1ul_rules
        text='A_HORIZONTAL,A,RoC,1,75.0,1,100.0\nA_HORIZONTAL,B,RoC,1,75.0,1,100.0\n2026-10-27_095950,27.10.2026,09:59:50,47,8,C1UL WS,-,A_HORIZONTAL,+,-64.9,867,697,95.6,867,710\n'
        records,errors,config=parse_config_csv(text.encode(),'2026-10-27_09.zone.C.csv')
        self.assertFalse(errors)
        rules=confirmed_c1ul_rules(config)
        self.assertEqual([r['upper'] for r in rules],[75,100])
        self.assertTrue(all(r['status']=='合格' for r in evaluate(records,rules)))
        config['rows'][1]['raw'][1]='76'
        with self.assertRaises(ValueError):confirmed_c1ul_rules(config)
