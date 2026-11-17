import unittest
import json
import random
from copy import deepcopy
from pathlib import Path
from engine import discover, intersection, validate
from reference import compare
from evaluate import score, read_gold

BASE=Path(__file__).resolve().parent


def scope(roles=('*',),countries=('*',),orgs=('*',),start='2027-01-01',end='2028-01-01'):
    return dict(roles=list(roles),jurisdictions=list(countries),organisations=list(orgs),start=start,end=end)


def fixture():
    sc=scope()
    return {'schema_version':'0.3','id':'test','snapshot_id':'test',
        'event':{'kind':'value_change','root_ko':'A','changed_fields':['amount'],'change_scope':deepcopy(sc),
                 'before':{'version_id':'A-old','scope':scope(start='2026-01-01',end='2027-01-01')},
                 'after':{'version_id':'A','text':'Amount 10','scope':deepcopy(sc)}},
        'nodes':[{'id':i,'title':i,'text':'Amount 10' if i=='A' else 'Uses the referenced amount','scope':deepcopy(sc),'source':'synthetic/test'} for i in 'ABCD'],
        'relationships':[{'id':a+b,'prerequisite':a,'dependent':b,'type':'DEPENDS_ON','field':'amount','scope':deepcopy(sc),'source':'synthetic/test','evidence':'Uses the referenced amount','certainty':'confirmed'} for a,b in [('A','B'),('B','C'),('C','D')]]}


def item(result,key):return next(i for i in result['items'] if i['ko_id']==key)


class TraversalTests(unittest.TestCase):
    def test_all_seven_reference_comparisons(self):
        for s in json.loads((BASE/'data/scenarios.json').read_text())['scenarios']:
            with self.subTest(s=s['id']):self.assertTrue(compare(s,discover(s))['matches'])

    def test_type_and_field_prevent_topic_match(self):
        s=fixture();s['relationships'][0]['type']='RELATED_TO'
        self.assertEqual(item(discover(s),'B')['status'],'No')
        self.assertEqual(item(discover(s,'untyped'),'B')['status'],'Yes')
        s['relationships'][0]['type']='DEPENDS_ON';s['relationships'][0]['field']='rate'
        self.assertEqual(item(discover(s),'B')['status'],'No')

    def test_accumulated_scope_vs_pairwise(self):
        s=fixture();s['relationships'][0]['scope']['jurisdictions']=['DE'];s['nodes'][3]['scope']['jurisdictions']=['FR']
        self.assertEqual(item(discover(s),'D')['status'],'No')
        self.assertEqual(item(discover(s,'local'),'D')['status'],'Yes')

    def test_adoption_changes_population_only_with_explicit_mapping(self):
        s=fixture();s['relationships'][0].update(type='ADOPTS_VALUE',mapping={'from':{'jurisdictions':['UK']},'to':{'jurisdictions':['IE']}})
        for field in ('before','after'):s['event'][field]['scope']['jurisdictions']=['UK']
        s['event']['change_scope']['jurisdictions']=['UK'];s['nodes'][0]['scope']['jurisdictions']=['UK'];s['nodes'][1]['scope']['jurisdictions']=['IE']
        self.assertEqual(item(discover(s),'B')['affected_scopes'][0]['jurisdictions'],['IE'])
        self.assertTrue(compare(s,discover(s))['matches'])
        s['relationships'][0]['mapping']['from']['jurisdictions']=['US']
        self.assertEqual(item(discover(s),'B')['status'],'No')

    def test_independent_override_stops_changed_amount(self):
        s=fixture();s['relationships'][0].update(type='OVERRIDES',override_mode='independent_value')
        self.assertEqual(item(discover(s),'B')['status'],'No')
        self.assertEqual(item(discover(s),'D')['status'],'No')

    def test_offset_dependency_keeps_propagating(self):
        s=fixture();s['relationships'][0]['evidence']='Pays the parent amount plus 100'
        self.assertEqual(item(discover(s),'D')['status'],'Yes')

    def test_conflicting_override_metadata_is_not_silently_ignored(self):
        s=fixture();e=deepcopy(s['relationships'][0]);e.update(id='override',type='OVERRIDES',override_mode='independent_value');s['relationships'].append(e)
        with self.assertRaisesRegex(ValueError,'Overlapping'):discover(s)

    def test_review_stop_selects_without_continuing(self):
        s=fixture();s['relationships'][0]['type']='REVIEW_ONLY'
        r=discover(s);self.assertEqual(item(r,'B')['status'],'Yes');self.assertEqual(item(r,'C')['status'],'No')
        self.assertTrue(compare(s,r)['matches'])

    def test_uncertainty_does_not_claim_a_scope(self):
        s=fixture();s['relationships'][0].update(certainty='uncertain',uncertainty_reason='reference unclear')
        r=discover(s);self.assertEqual(item(r,'D')['status'],'Defer');self.assertEqual(item(r,'D')['affected_scopes'],[])
        self.assertEqual(r['review_volume'],3);self.assertTrue(compare(s,r)['matches'])

    def test_definite_path_survives_an_uncertain_alternative(self):
        s=fixture();e=deepcopy(s['relationships'][0]);e.update(id='alternate',certainty='uncertain',uncertainty_reason='unclear');s['relationships'].append(e)
        r=discover(s);self.assertEqual(item(r,'B')['status'],'Yes');self.assertTrue(item(r,'B')['has_uncertainty'])

    def test_correlated_cells_do_not_create_cross_combinations(self):
        s=fixture();s['nodes'][1].pop('scope');s['nodes'][1]['scope_cells']=[scope(('manager',),('FR',)),scope(('engineer',),('DE',))]
        s['nodes'][2]['scope']=scope(('engineer',),('FR',))
        r=discover(s);self.assertEqual(len(item(r,'B')['affected_scopes']),2);self.assertEqual(item(r,'C')['status'],'No')
        self.assertTrue(compare(s,r)['matches'])

    def test_half_open_boundary(self):
        self.assertIsNone(intersection(scope(end='2027-02-01'),scope(start='2027-02-01')))
        s=fixture();s['relationships'][0]['scope']=scope(start='2026-01-01',end='2027-01-01')
        self.assertEqual(item(discover(s),'B')['status'],'No')

    def test_multiple_paths_direct_takes_precedence_without_losing_indirect(self):
        s=fixture();e=deepcopy(s['relationships'][0]);e.update(id='AC',dependent='C');s['relationships'].append(e)
        i=item(discover(s),'C');self.assertEqual(i['directness'],'direct');self.assertEqual({p['hops'] for p in i['paths']},{1,2})

    def test_cycle_and_depth_are_bounded(self):
        s=fixture();e=deepcopy(s['relationships'][0]);e.update(id='CA',prerequisite='C',dependent='A');s['relationships'].append(e)
        r=discover(s);self.assertNotIn('A',[i['ko_id'] for i in r['items']]);self.assertLess(r['visited_states'],10)
        self.assertEqual(item(discover(s,max_hops=2),'D')['status'],'No')

    def test_stable_order_and_no_input_mutation(self):
        s=fixture();saved=deepcopy(s);a=discover(s);self.assertEqual(s,saved)
        s['relationships'].reverse();b=discover(s)
        self.assertEqual(a['items'],b['items'])

    def test_rejects_unsupported_changes_and_relations(self):
        for key,value in [('kind','withdrawal'),('scope_change',True),('relationship_changes',['removed'])]:
            s=fixture();s['event'][key]=value
            with self.assertRaises(ValueError):discover(s)
        s=fixture();s['relationships'][0]['type']='EXCEPTION_TO'
        with self.assertRaises(ValueError):discover(s)

    def test_rejects_malformed_scope_and_duplicate_ids(self):
        for values in ([None],['*','manager'],['all_roles'],[]):
            s=fixture();s['nodes'][1]['scope']['roles']=values
            with self.assertRaises(ValueError):validate(s)
        s=fixture();s['nodes'].append(deepcopy(s['nodes'][1]))
        with self.assertRaises(ValueError):validate(s)

    def test_rejects_scope_contraction_without_flag(self):
        s=fixture();s['event']['before']['scope']['jurisdictions']=['FR','DE']
        with self.assertRaises(ValueError):discover(s)

    def test_small_graph_differential_check(self):
        rng=random.Random(241)
        for trial in range(40):
            s=fixture()
            for n in s['nodes'][1:]:n['scope']['jurisdictions']=rng.choice([['*'],['FR'],['DE'],['FR','DE']])
            for e in s['relationships']:
                e['scope']['roles']=rng.choice([['*'],['manager'],['engineer']])
                if rng.random()<.25:e.update(certainty='uncertain',uncertainty_reason='test uncertainty')
            with self.subTest(trial=trial):self.assertTrue(compare(s,discover(s))['matches'])


class EvaluationTests(unittest.TestCase):
    def test_deferral_is_not_a_true_positive(self):
        g={'a':{'label':'Yes'},'b':{'label':'No'},'c':{'label':'Ambiguous'}}
        r=score(g,{'a':'Defer','b':'Yes','c':'Defer'})
        self.assertEqual(r['recall'],0);self.assertEqual(r['review_capture_recall'],1);self.assertEqual(r['review_volume'],3)
        self.assertEqual(r['fp'],1);self.assertEqual(r['ambiguous_gold'],1)

    def test_missing_prediction_is_not_silently_dropped(self):
        with self.assertRaises(ValueError):score({'a':{'label':'Yes'}},{})

    def test_no_impact_event_has_undefined_recall(self):
        r=score({'a':{'label':'No'}},{'a':'No'})
        self.assertIsNone(r['recall']);self.assertIsNone(r['precision']);self.assertIsNone(r['f1'])
        self.assertEqual(r['review_volume'],0)

    def test_partial_directness_does_not_inflate_stratified_recall(self):
        r=score({'a':{'label':'Yes','directness':'direct'},'b':{'label':'Yes'}},{'a':'Yes','b':'No'})
        self.assertIsNone(r['direct_recall']);self.assertEqual(r['positive_gold_missing_directness'],1)

    def test_blank_workbook_is_not_gold(self):
        suite=json.loads((BASE/'data/scenarios.json').read_text())
        with self.assertRaisesRegex(ValueError,'freeze date'):read_gold(BASE/'3_Label_Matrix.xlsx',suite)


if __name__=='__main__':unittest.main()
