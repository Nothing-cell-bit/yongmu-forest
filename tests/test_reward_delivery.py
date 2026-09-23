import copy
import random
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'TwilightBossSliceB/TwilightBossSlice'))


def module():
    import reward_delivery
    return reward_delivery


class Engine:
    def __init__(self):
        self.saved = None
        self.save_ok = True
        self.chest_ok = True
        self.item_ok = True
        self.chests = []
        self.items = []
        self.slots = {}

    def save(self, data):
        if not self.save_ok:
            return False
        self.saved = copy.deepcopy(data)
        return True

    def chest(self, pos, dimension, table):
        if not self.chest_ok:
            return False
        self.chests.append((pos,dimension,table))
        return True

    def spawn(self, item, dimension, pos):
        if not self.item_ok:
            return False
        self.items.append((copy.deepcopy(item),dimension,pos))
        return 'item-id'

    def queue(self):
        return module().RewardDelivery(self.saved,self.save,self.chest,self.spawn,self.put)

    def put(self,item,dimension,pos,slot):
        if not self.item_ok:
            return False
        self.slots[(dimension,pos,slot)] = copy.deepcopy(item)
        return True


def test_chest_failure_survives_reload_and_does_not_consume_bonus():
    e = Engine(); e.chest_ok = False; q = e.queue()
    assert q.submit('naga',7,(1,2,3),'naga.json',[{'newItemName':'scale','count':3}])
    q.flush(); assert not e.items
    q = e.queue(); e.chest_ok = True; q.flush()
    assert len(e.chests) == 1 and len(e.items) == 1
    q = e.queue(); q.flush(); assert len(e.chests) == 1 and len(e.items) == 1


def test_failed_bonus_does_not_refill_or_replace_successful_chest():
    e = Engine(); e.item_ok = False; q = e.queue()
    q.submit('lich',7,(1,2,3),'lich.json',[{'newItemName':'bone','count':2}])
    q.flush(); assert len(e.chests) == 1
    q = e.queue(); e.item_ok = True; q.flush()
    assert len(e.chests) == 1 and len(e.items) == 1


def test_partial_ground_reward_resumes_at_failed_item():
    e = Engine(); count = [0]
    def spawn(item,dimension,pos):
        count[0] += 1
        return e.spawn(item,dimension,pos) if count[0] != 2 else False
    q = module().RewardDelivery(None,e.save,e.chest,spawn)
    q.submit('quest',7,(1,2,3),None,[{'newItemName':str(i),'count':1} for i in range(3)])
    q.flush(); assert len(e.items) == 1
    q=e.queue();q.flush()
    assert [v[0]['newItemName'] for v in e.items] == ['0','1','2']


def test_save_failure_prevents_effects_until_durable():
    e=Engine();e.save_ok=False;q=e.queue()
    assert not q.submit('knight',7,(1,2,3),'knight.json',[])
    q.flush();assert not e.chests
    e.save_ok=True;q.flush();assert len(e.chests)==1


def test_repeated_submission_does_not_reroll_or_repeat():
    e=Engine();q=e.queue()
    q.submit('same',7,(1,2,3),None,[{'newItemName':'soup','count':2}]);q.flush()
    q.submit('same',7,(1,2,3),None,[{'newItemName':'soup','count':5}]);q.flush()
    assert len(e.items)==1 and e.items[0][0]['count']==2


@pytest.mark.parametrize('kind,expected',[
    ('naga',{'tf_slice:naga_scale':3}),
    ('lich',{'minecraft:ender_pearl':3,'minecraft:bone':3}),
    ('ur_ghast',{'tf_slice:carminite':12,'tf_slice:fiery_tears':6})])
def test_looting_adds_per_pool_roll_with_java_rounding(kind,expected):
    class MaxRoll:
        def uniform(self,a,b):return b
    items=module().bonus_items(kind,3,MaxRoll())
    assert {i['newItemName']:i['count'] for i in items}==expected
    assert module().bonus_items(kind,0,MaxRoll())==[]


def test_minoshroom_rewards_exist_without_participant_and_have_per_roll_looting():
    class MaxRoll:
        def randint(self,a,b):return b
        def uniform(self,a,b):return b
    items=module().minoshroom_items(3,MaxRoll())
    counts={}
    for i in items:
        counts[i['newItemName']]=counts.get(i['newItemName'],0)+i['count']
        assert i['count']==1  # Soup and boss equipment are non-stackable.
    assert counts=={'tf_slice:meef_stroganoff':20,'tf_slice:minoshroom_trophy_item':1,
        'tf_slice:diamond_minotaur_axe':1}


def test_empty_or_failed_item_ids_are_not_accepted():
    for result in [None,False,'', '-1',-1]:
        e=Engine();q=module().RewardDelivery(None,e.save,e.chest,lambda *args:result)
        q.submit('item',7,(1,2,3),None,[{'newItemName':'x','count':1}]);q.flush()
        assert not e.saved['item']['complete']


def test_work_per_flush_is_bounded():
    e=Engine();q=e.queue()
    for i in range(20):q.submit(str(i),7,(1,2,3),None,[{'newItemName':'x','count':1}])
    q.flush(limit=4);assert len(e.items)==4


def test_exception_is_retried_without_aborting_other_rewards():
    e=Engine()
    def spawn(item,*args):
        if item['newItemName']=='bad':raise RuntimeError('not loaded')
        return e.spawn(item,*args)
    q=module().RewardDelivery(None,e.save,e.chest,spawn)
    for name in ['bad','good']:q.submit(name,7,(1,2,3),None,[{'newItemName':name,'count':1}])
    q.flush();assert len(e.items)==1


def test_unloaded_chests_do_not_starve_later_rewards():
    e=Engine();e.chest_ok=False;q=e.queue()
    for i in range(10):q.submit('a'+str(i),7,(1,2,3),'blocked.json',[])
    q.submit('z',7,(1,2,3),None,[{'newItemName':'x','count':1}])
    q.flush(limit=4);q.flush(limit=4);q.flush(limit=4)
    assert len(e.items)==1


def test_itemized_chest_resumes_without_replacing_chest_or_spawning_ground_items():
    e=Engine();q=e.queue();e.item_ok=False
    q.submit('mino',7,(1,2,3),'',[{'newItemName':'soup','count':1},
        {'newItemName':'axe','count':1}],container_items=True)
    q.flush();assert len(e.chests)==1 and not e.slots
    e.item_ok=True;q=e.queue();q.flush()
    assert len(e.chests)==1 and len(e.slots)==2 and not e.items
    q.flush();assert len(e.slots)==2


def test_itemized_chest_overflow_keeps_items_above_27_slots():
    e=Engine();q=e.queue()
    q.submit('overflow',7,(1,2,3),'',[{'newItemName':'soup','count':1} for _ in range(30)],container_items=True)
    q.flush(limit=40)
    assert len(e.slots)==27 and len(e.items)==3
