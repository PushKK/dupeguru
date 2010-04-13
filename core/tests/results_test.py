# Created By: Virgil Dupras
# Created On: 2006/02/23
# $Id$                                  
# Copyright 2010 Hardcoded Software (http://www.hardcoded.net)
# 
# This software is licensed under the "HS" License as described in the "LICENSE" file, 
# which should be included with this package. The terms are also available at 
# http://www.hardcoded.net/licenses/hs_license

import StringIO
import os.path as op

from lxml import etree
from nose.tools import eq_

from hsutil.path import Path
from hsutil.testcase import TestCase
from hsutil.misc import first

from . import engine_test, data
from .. import engine
from ..results import Results

class NamedObject(engine_test.NamedObject):
    path = property(lambda x:Path('basepath') + x.name)
    is_ref = False
    
    def __nonzero__(self):
        return False #Make sure that operations are made correctly when the bool value of files is false.

# Returns a group set that looks like that:
# "foo bar" (1)
#   "bar bleh" (1024)
#   "foo bleh" (1)
# "ibabtu" (1)
#   "ibabtu" (1)
def GetTestGroups():
    objects = [NamedObject("foo bar"),NamedObject("bar bleh"),NamedObject("foo bleh"),NamedObject("ibabtu"),NamedObject("ibabtu")]
    objects[1].size = 1024
    matches = engine.getmatches(objects) #we should have 5 matches
    groups = engine.get_groups(matches) #We should have 2 groups
    for g in groups:
        g.prioritize(lambda x:objects.index(x)) #We want the dupes to be in the same order as the list is
    groups.sort(key=len, reverse=True) # We want the group with 3 members to be first.
    return (objects,matches,groups)

class TCResultsEmpty(TestCase):
    def setUp(self):
        self.results = Results(data)
    
    def test_apply_invalid_filter(self):
        # If the applied filter is an invalid regexp, just ignore the filter.
        self.results.apply_filter('[') # invalid
        self.test_stat_line() # make sure that the stats line isn't saying we applied a '[' filter
    
    def test_stat_line(self):
        self.assertEqual("0 / 0 (0.00 B / 0.00 B) duplicates marked.",self.results.stat_line)
    
    def test_groups(self):
        self.assertEqual(0,len(self.results.groups))
    
    def test_get_group_of_duplicate(self):
        self.assert_(self.results.get_group_of_duplicate('foo') is None)
    
    def test_save_to_xml(self):
        f = StringIO.StringIO()
        self.results.save_to_xml(f)
        f.seek(0)
        doc = etree.parse(f)
        root = doc.getroot()
        self.assertEqual('results', root.tag)
    

class TCResultsWithSomeGroups(TestCase):
    def setUp(self):
        self.results = Results(data)
        self.objects,self.matches,self.groups = GetTestGroups()
        self.results.groups = self.groups
    
    def test_stat_line(self):
        self.assertEqual("0 / 3 (0.00 B / 1.01 KB) duplicates marked.",self.results.stat_line)
    
    def test_groups(self):
        self.assertEqual(2,len(self.results.groups))
    
    def test_get_group_of_duplicate(self):
        for o in self.objects:
            g = self.results.get_group_of_duplicate(o)
            self.assert_(isinstance(g, engine.Group))
            self.assert_(o in g)
        self.assert_(self.results.get_group_of_duplicate(self.groups[0]) is None)
    
    def test_remove_duplicates(self):
        g1,g2 = self.results.groups
        self.results.remove_duplicates([g1.dupes[0]])
        self.assertEqual(2,len(g1))
        self.assert_(g1 in self.results.groups)
        self.results.remove_duplicates([g1.ref])
        self.assertEqual(2,len(g1))
        self.assert_(g1 in self.results.groups)
        self.results.remove_duplicates([g1.dupes[0]])
        self.assertEqual(0,len(g1))
        self.assert_(g1 not in self.results.groups)
        self.results.remove_duplicates([g2.dupes[0]])
        self.assertEqual(0,len(g2))
        self.assert_(g2 not in self.results.groups)
        self.assertEqual(0,len(self.results.groups))
    
    def test_remove_duplicates_with_ref_files(self):
        g1,g2 = self.results.groups
        self.objects[0].is_ref = True
        self.objects[1].is_ref = True
        self.results.remove_duplicates([self.objects[2]])
        self.assertEqual(0,len(g1))
        self.assert_(g1 not in self.results.groups)
    
    def test_make_ref(self):
        g = self.results.groups[0]
        d = g.dupes[0]
        self.results.make_ref(d)
        self.assert_(d is g.ref)
    
    def test_sort_groups(self):
        self.results.make_ref(self.objects[1]) #We want to make the 1024 sized object to go ref.
        g1,g2 = self.groups
        self.results.sort_groups(2) #2 is the key for size
        self.assert_(self.results.groups[0] is g2)
        self.assert_(self.results.groups[1] is g1)
        self.results.sort_groups(2,False)
        self.assert_(self.results.groups[0] is g1)
        self.assert_(self.results.groups[1] is g2)
    
    def test_set_groups_when_sorted(self):
        self.results.make_ref(self.objects[1]) #We want to make the 1024 sized object to go ref.
        self.results.sort_groups(2)
        objects,matches,groups = GetTestGroups()
        g1,g2 = groups
        g1.switch_ref(objects[1])
        self.results.groups = groups
        self.assert_(self.results.groups[0] is g2)
        self.assert_(self.results.groups[1] is g1)
    
    def test_get_dupe_list(self):
        self.assertEqual([self.objects[1],self.objects[2],self.objects[4]],self.results.dupes)
    
    def test_dupe_list_is_cached(self):
        self.assert_(self.results.dupes is self.results.dupes)
    
    def test_dupe_list_cache_is_invalidated_when_needed(self):
        o1,o2,o3,o4,o5 = self.objects
        self.assertEqual([o2,o3,o5],self.results.dupes)
        self.results.make_ref(o2)
        self.assertEqual([o1,o3,o5],self.results.dupes)
        objects,matches,groups = GetTestGroups()
        o1,o2,o3,o4,o5 = objects
        self.results.groups = groups
        self.assertEqual([o2,o3,o5],self.results.dupes)
    
    def test_dupe_list_sort(self):
        o1,o2,o3,o4,o5 = self.objects
        o1.size = 5
        o2.size = 4
        o3.size = 3
        o4.size = 2
        o5.size = 1
        self.results.sort_dupes(2)
        self.assertEqual([o5,o3,o2],self.results.dupes)
        self.results.sort_dupes(2,False)
        self.assertEqual([o2,o3,o5],self.results.dupes)
    
    def test_dupe_list_remember_sort(self):
        o1,o2,o3,o4,o5 = self.objects
        o1.size = 5
        o2.size = 4
        o3.size = 3
        o4.size = 2
        o5.size = 1
        self.results.sort_dupes(2)
        self.results.make_ref(o2)
        self.assertEqual([o5,o3,o1],self.results.dupes)
    
    def test_dupe_list_sort_delta_values(self):
        o1,o2,o3,o4,o5 = self.objects
        o1.size = 10
        o2.size = 2 #-8
        o3.size = 3 #-7
        o4.size = 20
        o5.size = 1 #-19
        self.results.sort_dupes(2,delta=True)
        self.assertEqual([o5,o2,o3],self.results.dupes)
    
    def test_sort_empty_list(self):
        #There was an infinite loop when sorting an empty list.
        r = Results(data)
        r.sort_dupes(0)
        self.assertEqual([],r.dupes)
    
    def test_dupe_list_update_on_remove_duplicates(self):
        o1,o2,o3,o4,o5 = self.objects
        self.assertEqual(3,len(self.results.dupes))
        self.results.remove_duplicates([o2])
        self.assertEqual(2,len(self.results.dupes))
    

class TCResultsMarkings(TestCase):
    def setUp(self):
        self.results = Results(data)
        self.objects,self.matches,self.groups = GetTestGroups()
        self.results.groups = self.groups
    
    def test_stat_line(self):
        self.assertEqual("0 / 3 (0.00 B / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.mark(self.objects[1])
        self.assertEqual("1 / 3 (1.00 KB / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.mark_invert()
        self.assertEqual("2 / 3 (2.00 B / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.mark_invert()
        self.results.unmark(self.objects[1])
        self.results.mark(self.objects[2])
        self.results.mark(self.objects[4])
        self.assertEqual("2 / 3 (2.00 B / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.mark(self.objects[0]) #this is a ref, it can't be counted
        self.assertEqual("2 / 3 (2.00 B / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.groups = self.groups
        self.assertEqual("0 / 3 (0.00 B / 1.01 KB) duplicates marked.",self.results.stat_line)
    
    def test_with_ref_duplicate(self):
        self.objects[1].is_ref = True
        self.results.groups = self.groups
        self.assert_(not self.results.mark(self.objects[1]))
        self.results.mark(self.objects[2])
        self.assertEqual("1 / 2 (1.00 B / 2.00 B) duplicates marked.",self.results.stat_line)
    
    def test_perform_on_marked(self):
        def log_object(o):
            log.append(o)
            return True
        
        log = []
        self.results.mark_all()
        self.results.perform_on_marked(log_object,False)
        self.assert_(self.objects[1] in log)
        self.assert_(self.objects[2] in log)
        self.assert_(self.objects[4] in log)
        self.assertEqual(3,len(log))
        log = []
        self.results.mark_none()
        self.results.mark(self.objects[4])
        self.results.perform_on_marked(log_object,True)
        self.assertEqual(1,len(log))
        self.assert_(self.objects[4] in log)
        self.assertEqual(1,len(self.results.groups))
    
    def test_perform_on_marked_with_problems(self):
        def log_object(o):
            log.append(o)
            if o is self.objects[1]:
                raise EnvironmentError('foobar')
        
        log = []
        self.results.mark_all()
        assert self.results.is_marked(self.objects[1])
        self.results.perform_on_marked(log_object, True)
        eq_(len(log), 3)
        eq_(len(self.results.groups), 1)
        eq_(len(self.results.groups[0]), 2)
        assert self.objects[1] in self.results.groups[0]
        assert not self.results.is_marked(self.objects[2])
        assert self.results.is_marked(self.objects[1])
        eq_(len(self.results.problems), 1)
        dupe, msg = self.results.problems[0]
        assert dupe is self.objects[1]
        eq_(msg, 'foobar')
    
    def test_perform_on_marked_with_ref(self):
        def log_object(o):
            log.append(o)
            return True
        
        log = []
        self.objects[0].is_ref = True
        self.objects[1].is_ref = True
        self.results.mark_all()
        self.results.perform_on_marked(log_object,True)
        self.assert_(self.objects[1] not in log)
        self.assert_(self.objects[2] in log)
        self.assert_(self.objects[4] in log)
        self.assertEqual(2,len(log))
        self.assertEqual(0,len(self.results.groups))
    
    def test_perform_on_marked_remove_objects_only_at_the_end(self):
        def check_groups(o):
            self.assertEqual(3,len(g1))
            self.assertEqual(2,len(g2))
            return True
        
        g1,g2 = self.results.groups
        self.results.mark_all()
        self.results.perform_on_marked(check_groups,True)
        self.assertEqual(0,len(g1))
        self.assertEqual(0,len(g2))
        self.assertEqual(0,len(self.results.groups))
    
    def test_remove_duplicates(self):
        g1 = self.results.groups[0]
        g2 = self.results.groups[1]
        self.results.mark(g1.dupes[0])
        self.assertEqual("1 / 3 (1.00 KB / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.remove_duplicates([g1.dupes[1]])
        self.assertEqual("1 / 2 (1.00 KB / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.remove_duplicates([g1.dupes[0]])
        self.assertEqual("0 / 1 (0.00 B / 1.00 B) duplicates marked.",self.results.stat_line)
    
    def test_make_ref(self):
        g = self.results.groups[0]
        d = g.dupes[0]
        self.results.mark(d)
        self.assertEqual("1 / 3 (1.00 KB / 1.01 KB) duplicates marked.",self.results.stat_line)
        self.results.make_ref(d)
        self.assertEqual("0 / 3 (0.00 B / 3.00 B) duplicates marked.",self.results.stat_line)
        self.results.make_ref(d)
        self.assertEqual("0 / 3 (0.00 B / 3.00 B) duplicates marked.",self.results.stat_line)
    
    def test_SaveXML(self):
        self.results.mark(self.objects[1])
        self.results.mark_invert()
        f = StringIO.StringIO()
        self.results.save_to_xml(f)
        f.seek(0)
        doc = etree.parse(f)
        root = doc.getroot()
        g1, g2 = root.iterchildren('group')
        d1, d2, d3 = g1.iterchildren('file')
        self.assertEqual('n', d1.get('marked'))
        self.assertEqual('n', d2.get('marked'))
        self.assertEqual('y', d3.get('marked'))
        d1, d2 = g2.iterchildren('file')
        self.assertEqual('n', d1.get('marked'))
        self.assertEqual('y', d2.get('marked'))
    
    def test_LoadXML(self):
        def get_file(path):
            return [f for f in self.objects if str(f.path) == path][0]
        
        self.objects[4].name = 'ibabtu 2' #we can't have 2 files with the same path
        self.results.mark(self.objects[1])
        self.results.mark_invert()
        f = StringIO.StringIO()
        self.results.save_to_xml(f)
        f.seek(0)
        r = Results(data)
        r.load_from_xml(f,get_file)
        self.assert_(not r.is_marked(self.objects[0]))
        self.assert_(not r.is_marked(self.objects[1]))
        self.assert_(r.is_marked(self.objects[2]))
        self.assert_(not r.is_marked(self.objects[3]))
        self.assert_(r.is_marked(self.objects[4]))
    

class TCResultsXML(TestCase):
    def setUp(self):
        self.results = Results(data)
        self.objects, self.matches, self.groups = GetTestGroups()
        self.results.groups = self.groups
    
    def get_file(self, path): # use this as a callback for load_from_xml
        return [o for o in self.objects if o.path == path][0]
    
    def test_save_to_xml(self):
        self.objects[0].is_ref = True
        self.objects[0].words = [['foo','bar']]
        f = StringIO.StringIO()
        self.results.save_to_xml(f)
        f.seek(0)
        doc = etree.parse(f)
        root = doc.getroot()
        self.assertEqual('results', root.tag)
        self.assertEqual(2, len(root))
        self.assertEqual(2, len([c for c in root if c.tag == 'group']))
        g1, g2 = root
        self.assertEqual(6,len(g1))
        self.assertEqual(3,len([c for c in g1 if c.tag == 'file']))
        self.assertEqual(3,len([c for c in g1 if c.tag == 'match']))
        d1, d2, d3 = [c for c in g1 if c.tag == 'file']
        self.assertEqual(op.join('basepath','foo bar'),d1.get('path'))
        self.assertEqual(op.join('basepath','bar bleh'),d2.get('path'))
        self.assertEqual(op.join('basepath','foo bleh'),d3.get('path'))
        self.assertEqual('y',d1.get('is_ref'))
        self.assertEqual('n',d2.get('is_ref'))
        self.assertEqual('n',d3.get('is_ref'))
        self.assertEqual('foo,bar',d1.get('words'))
        self.assertEqual('bar,bleh',d2.get('words'))
        self.assertEqual('foo,bleh',d3.get('words'))
        self.assertEqual(3,len(g2))
        self.assertEqual(2,len([c for c in g2 if c.tag == 'file']))
        self.assertEqual(1,len([c for c in g2 if c.tag == 'match']))
        d1, d2 = [c for c in g2 if c.tag == 'file']
        self.assertEqual(op.join('basepath','ibabtu'),d1.get('path'))
        self.assertEqual(op.join('basepath','ibabtu'),d2.get('path'))
        self.assertEqual('n',d1.get('is_ref'))
        self.assertEqual('n',d2.get('is_ref'))
        self.assertEqual('ibabtu',d1.get('words'))
        self.assertEqual('ibabtu',d2.get('words'))
    
    def test_LoadXML(self):
        def get_file(path):
            return [f for f in self.objects if str(f.path) == path][0]
        
        self.objects[0].is_ref = True
        self.objects[4].name = 'ibabtu 2' #we can't have 2 files with the same path
        f = StringIO.StringIO()
        self.results.save_to_xml(f)
        f.seek(0)
        r = Results(data)
        r.load_from_xml(f,get_file)
        self.assertEqual(2,len(r.groups))
        g1,g2 = r.groups
        self.assertEqual(3,len(g1))
        self.assert_(g1[0].is_ref)
        self.assert_(not g1[1].is_ref)
        self.assert_(not g1[2].is_ref)
        self.assert_(g1[0] is self.objects[0])
        self.assert_(g1[1] is self.objects[1])
        self.assert_(g1[2] is self.objects[2])
        self.assertEqual(['foo','bar'],g1[0].words)
        self.assertEqual(['bar','bleh'],g1[1].words)
        self.assertEqual(['foo','bleh'],g1[2].words)
        self.assertEqual(2,len(g2))
        self.assert_(not g2[0].is_ref)
        self.assert_(not g2[1].is_ref)
        self.assert_(g2[0] is self.objects[3])
        self.assert_(g2[1] is self.objects[4])
        self.assertEqual(['ibabtu'],g2[0].words)
        self.assertEqual(['ibabtu'],g2[1].words)
    
    def test_LoadXML_with_filename(self):
        def get_file(path):
            return [f for f in self.objects if str(f.path) == path][0]
        
        filename = op.join(self.tmpdir(), 'dupeguru_results.xml')
        self.objects[4].name = 'ibabtu 2' #we can't have 2 files with the same path
        self.results.save_to_xml(filename)
        r = Results(data)
        r.load_from_xml(filename,get_file)
        self.assertEqual(2,len(r.groups))
    
    def test_LoadXML_with_some_files_that_dont_exist_anymore(self):
        def get_file(path):
            if path.endswith('ibabtu 2'):
                return None
            return [f for f in self.objects if str(f.path) == path][0]
        
        self.objects[4].name = 'ibabtu 2' #we can't have 2 files with the same path
        f = StringIO.StringIO()
        self.results.save_to_xml(f)
        f.seek(0)
        r = Results(data)
        r.load_from_xml(f,get_file)
        self.assertEqual(1,len(r.groups))
        self.assertEqual(3,len(r.groups[0]))
    
    def test_LoadXML_missing_attributes_and_bogus_elements(self):
        def get_file(path):
            return [f for f in self.objects if str(f.path) == path][0]
        
        root = etree.Element('foobar') #The root element shouldn't matter, really.
        group_node = etree.SubElement(root, 'group')
        dupe_node = etree.SubElement(group_node, 'file') #Perfectly correct file
        dupe_node.set('path', op.join('basepath','foo bar'))
        dupe_node.set('is_ref', 'y')
        dupe_node.set('words', 'foo,bar')
        dupe_node = etree.SubElement(group_node, 'file') #is_ref missing, default to 'n'
        dupe_node.set('path',op.join('basepath','foo bleh'))
        dupe_node.set('words','foo,bleh')
        dupe_node = etree.SubElement(group_node, 'file') #words are missing, valid.
        dupe_node.set('path',op.join('basepath','bar bleh'))
        dupe_node = etree.SubElement(group_node, 'file') #path is missing, invalid.
        dupe_node.set('words','foo,bleh')
        dupe_node = etree.SubElement(group_node, 'foobar') #Invalid element name
        dupe_node.set('path',op.join('basepath','bar bleh'))
        dupe_node.set('is_ref','y')
        dupe_node.set('words','bar,bleh')
        match_node = etree.SubElement(group_node, 'match') # match pointing to a bad index
        match_node.set('first', '42')
        match_node.set('second', '45')
        match_node = etree.SubElement(group_node, 'match') # match with missing attrs
        match_node = etree.SubElement(group_node, 'match') # match with non-int values
        match_node.set('first', 'foo')
        match_node.set('second', 'bar')
        match_node.set('percentage', 'baz')
        group_node = etree.SubElement(root, 'foobar') #invalid group
        group_node = etree.SubElement(root, 'group') #empty group
        f = StringIO.StringIO()
        tree = etree.ElementTree(root)
        tree.write(f, encoding='utf-8')
        f.seek(0)
        r = Results(data)
        r.load_from_xml(f, get_file)
        self.assertEqual(1,len(r.groups))
        self.assertEqual(3,len(r.groups[0]))
    
    def test_xml_non_ascii(self):
        def get_file(path):
            if path == op.join('basepath',u'\xe9foo bar'):
                return objects[0]
            if path == op.join('basepath',u'bar bleh'):
                return objects[1]
        
        objects = [NamedObject(u"\xe9foo bar",True),NamedObject("bar bleh",True)]
        matches = engine.getmatches(objects) #we should have 5 matches
        groups = engine.get_groups(matches) #We should have 2 groups
        for g in groups:
            g.prioritize(lambda x:objects.index(x)) #We want the dupes to be in the same order as the list is
        results = Results(data)
        results.groups = groups
        f = StringIO.StringIO()
        results.save_to_xml(f)
        f.seek(0)
        r = Results(data)
        r.load_from_xml(f,get_file)
        g = r.groups[0]
        self.assertEqual(u"\xe9foo bar",g[0].name)
        self.assertEqual(['efoo','bar'],g[0].words)
    
    def test_load_invalid_xml(self):
        f = StringIO.StringIO()
        f.write('<this is invalid')
        f.seek(0)
        r = Results(data)
        r.load_from_xml(f,None)
        self.assertEqual(0,len(r.groups))
    
    def test_load_non_existant_xml(self):
        r = Results(data)
        try:
            r.load_from_xml('does_not_exist.xml', None)
        except IOError:
            self.fail()
        self.assertEqual(0,len(r.groups))
    
    def test_remember_match_percentage(self):
        group = self.groups[0]
        d1, d2, d3 = group
        fake_matches = set()
        fake_matches.add(engine.Match(d1, d2, 42))
        fake_matches.add(engine.Match(d1, d3, 43))
        fake_matches.add(engine.Match(d2, d3, 46))
        group.matches = fake_matches
        f = StringIO.StringIO()
        results = self.results
        results.save_to_xml(f)
        f.seek(0)
        results = Results(data)
        results.load_from_xml(f, self.get_file)
        group = results.groups[0]
        d1, d2, d3 = group
        match = group.get_match_of(d2) #d1 - d2
        self.assertEqual(42, match[2])
        match = group.get_match_of(d3) #d1 - d3
        self.assertEqual(43, match[2])
        group.switch_ref(d2)
        match = group.get_match_of(d3) #d2 - d3
        self.assertEqual(46, match[2])
    
    def test_save_and_load(self):
        # previously, when reloading matches, they wouldn't be reloaded as namedtuples
        f = StringIO.StringIO()
        self.results.save_to_xml(f)
        f.seek(0)
        self.results.load_from_xml(f, self.get_file)
        first(self.results.groups[0].matches).percentage
    
    def test_apply_filter_works_on_paths(self):
        # apply_filter() searches on the whole path, not just on the filename.
        self.results.apply_filter(u'basepath')
        eq_(len(self.results.groups), 2)

class TCResultsFilter(TestCase):
    def setUp(self):
        self.results = Results(data)
        self.objects, self.matches, self.groups = GetTestGroups()
        self.results.groups = self.groups
        self.results.apply_filter(r'foo')
    
    def test_groups(self):
        self.assertEqual(1, len(self.results.groups))
        self.assert_(self.results.groups[0] is self.groups[0])
    
    def test_dupes(self):
        # There are 2 objects matching. The first one is ref. Only the 3rd one is supposed to be in dupes.
        self.assertEqual(1, len(self.results.dupes))
        self.assert_(self.results.dupes[0] is self.objects[2])
    
    def test_cancel_filter(self):
        self.results.apply_filter(None)
        self.assertEqual(3, len(self.results.dupes))
        self.assertEqual(2, len(self.results.groups))
    
    def test_dupes_reconstructed_filtered(self):
        # make_ref resets self.__dupes to None. When it's reconstructed, we want it filtered
        dupe = self.results.dupes[0] #3rd object
        self.results.make_ref(dupe)
        self.assertEqual(1, len(self.results.dupes))
        self.assert_(self.results.dupes[0] is self.objects[0])
    
    def test_include_ref_dupes_in_filter(self):
        # When only the ref of a group match the filter, include it in the group
        self.results.apply_filter(None)
        self.results.apply_filter(r'foo bar')
        self.assertEqual(1, len(self.results.groups))
        self.assertEqual(0, len(self.results.dupes))
    
    def test_filters_build_on_one_another(self):
        self.results.apply_filter(r'bar')
        self.assertEqual(1, len(self.results.groups))
        self.assertEqual(0, len(self.results.dupes))
    
    def test_stat_line(self):
        expected = '0 / 1 (0.00 B / 1.00 B) duplicates marked. filter: foo'
        self.assertEqual(expected, self.results.stat_line)
        self.results.apply_filter(r'bar')
        expected = '0 / 0 (0.00 B / 0.00 B) duplicates marked. filter: foo --> bar'
        self.assertEqual(expected, self.results.stat_line)
        self.results.apply_filter(None)
        expected = '0 / 3 (0.00 B / 1.01 KB) duplicates marked.'
        self.assertEqual(expected, self.results.stat_line)
    
    def test_mark_count_is_filtered_as_well(self):
        self.results.apply_filter(None)
        # We don't want to perform mark_all() because we want the mark list to contain objects
        for dupe in self.results.dupes:
            self.results.mark(dupe)
        self.results.apply_filter(r'foo')
        expected = '1 / 1 (1.00 B / 1.00 B) duplicates marked. filter: foo'
        self.assertEqual(expected, self.results.stat_line)
    
    def test_sort_groups(self):
        self.results.apply_filter(None)
        self.results.make_ref(self.objects[1]) # to have the 1024 b obkect as ref
        g1,g2 = self.groups
        self.results.apply_filter('a') # Matches both group
        self.results.sort_groups(2) #2 is the key for size
        self.assert_(self.results.groups[0] is g2)
        self.assert_(self.results.groups[1] is g1)
        self.results.apply_filter(None)
        self.assert_(self.results.groups[0] is g2)
        self.assert_(self.results.groups[1] is g1)
        self.results.sort_groups(2, False)
        self.results.apply_filter('a')
        self.assert_(self.results.groups[1] is g2)
        self.assert_(self.results.groups[0] is g1)
    
    def test_set_group(self):
        #We want the new group to be filtered
        self.objects, self.matches, self.groups = GetTestGroups()
        self.results.groups = self.groups
        self.assertEqual(1, len(self.results.groups))
        self.assert_(self.results.groups[0] is self.groups[0])
    
    def test_load_cancels_filter(self):
        def get_file(path):
            return [f for f in self.objects if str(f.path) == path][0]
        
        filename = op.join(self.tmpdir(), 'dupeguru_results.xml')
        self.objects[4].name = 'ibabtu 2' #we can't have 2 files with the same path
        self.results.save_to_xml(filename)
        r = Results(data)
        r.apply_filter('foo')
        r.load_from_xml(filename,get_file)
        self.assertEqual(2,len(r.groups))
    
    def test_remove_dupe(self):
        self.results.remove_duplicates([self.results.dupes[0]])
        self.results.apply_filter(None)
        self.assertEqual(2,len(self.results.groups))
        self.assertEqual(2,len(self.results.dupes))
        self.results.apply_filter('ibabtu')
        self.results.remove_duplicates([self.results.dupes[0]])
        self.results.apply_filter(None)
        self.assertEqual(1,len(self.results.groups))
        self.assertEqual(1,len(self.results.dupes))
    
    def test_filter_is_case_insensitive(self):
        self.results.apply_filter(None)
        self.results.apply_filter('FOO')
        self.assertEqual(1, len(self.results.dupes))
    
    def test_make_ref_on_filtered_out_doesnt_mess_stats(self):
        # When filtered, a group containing filtered out dupes will display them as being reference.
        # When calling make_ref on such a dupe, the total size and dupecount stats gets messed up
        # because they are *not* counted in the stats in the first place.
        g1, g2 = self.groups
        bar_bleh = g1[1] # The "bar bleh" dupe is filtered out
        self.results.make_ref(bar_bleh)
        # Now the stats should display *2* markable dupes (instead of 1)
        expected = '0 / 2 (0.00 B / 2.00 B) duplicates marked. filter: foo'
        self.assertEqual(expected, self.results.stat_line)
        self.results.apply_filter(None) # Now let's make sure our unfiltered results aren't fucked up
        expected = '0 / 3 (0.00 B / 3.00 B) duplicates marked.'
        self.assertEqual(expected, self.results.stat_line)
    

class TCResultsRefFile(TestCase):
    def setUp(self):
        self.results = Results(data)
        self.objects, self.matches, self.groups = GetTestGroups()
        self.objects[0].is_ref = True
        self.objects[1].is_ref = True
        self.results.groups = self.groups
    
    def test_stat_line(self):
        expected = '0 / 2 (0.00 B / 2.00 B) duplicates marked.'
        self.assertEqual(expected, self.results.stat_line)
    
    def test_make_ref(self):
        d = self.results.groups[0].dupes[1] #non-ref
        r = self.results.groups[0].ref
        self.results.make_ref(d)
        expected = '0 / 1 (0.00 B / 1.00 B) duplicates marked.'
        self.assertEqual(expected, self.results.stat_line)
        self.results.make_ref(r)
        expected = '0 / 2 (0.00 B / 2.00 B) duplicates marked.'
        self.assertEqual(expected, self.results.stat_line)
    
