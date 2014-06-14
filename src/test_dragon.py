import sys
import unittest
import bgp_sim
import itertools
import random
import networkx as nx
from utils import output_configuration, compute_aggregate

config_dir = '../configs/'

active_tests = {
	'testMultipleConvergenceEvent' : True,
	'testSimpleTriangleForAggregates' : True,
	'testConvergenceEventBGPOnly' : True,
	'testSimpleTriangleWithFailedLink' : True,
	'testSimpleTriangle' : True,
	'testSimpleChainWithOneASAnnouncingParentChild': True,
	'testSimpleChain' : True,
	'testRouteConsistencyFiltering' : True,
	'testFwdConsistencyFiltering' : True,
	'testGenerateAggregatesForNonCoveredPrefixes' : True,
	'testGenerateAggregatesForNonCoveredPrefixesWithFailure' : True,
	'testGenerateAggregatesForNonCoveredPrefixesWithFailureAndBack' : True,
	'testMultipleLevelRouteConsistency' : True,
	'testConvergenceEvent' : True,
	'testMultipleLevelForwardingConsistency' : True,
	'testAnycastAnnouncementOfAggregate' : True,
	'testAggregatesComputation' : False
}

class DragonTest(unittest.TestCase):
	
	def setUp(self):
		# Make sure that DRAGON is activated
		bgp_sim.DRAGON_ACTIVATED = True
		bgp_sim.RESTRICT_AGGREGATES_TO_PARENTLESS_PREFIXES = True
		bgp_sim.DISABLE_DEAGGREGATES_ANNOUNCEMENT = False
		# Activate DEBUG
		#bgp_sim.activate_debug()
	
	def testSimpleTriangleForAggregates(self):
		
		if active_tests['testSimpleTriangleForAggregates']:
			
			print "Running testSimpleTriangleForAggregates ..."
			
			#for (a,b) in itertools.permutations([1,2]):
			for (a,b) in [(1,2)]:
			
				child1 = '1.0.0.0/24'
				child2 = '1.0.1.0/24'
				
				bgp_topology = nx.DiGraph()
				
				## Edge (3,1)
				bgp_topology.add_edge(3, 1, type = 1)
				bgp_topology.add_edge(1, 3, type = 3)
				
				## Edge (3,2)
				bgp_topology.add_edge(3, 2, type = 1)
				bgp_topology.add_edge(2, 3, type = 3)
				
				## Edge (4,3)
				bgp_topology.add_edge(4, 3, type = 1)
				bgp_topology.add_edge(3, 4, type = 3)
				
				sim_config = output_configuration(bgp_topology)
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				
				bgp_sim.loadConfig(sim_config)
				
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['1.1', child1], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['2.1', child2], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim.run()
	
	def testSimpleTriangle(self):
		
		if active_tests['testSimpleTriangle']:
			
			print "Running testSimpleTriangle ..."
			
			for (a,b) in itertools.permutations([1,2]):
			
				parent = '1.0.0.0/22'
				child = '1.0.0.0/24'
				
				bgp_topology = nx.DiGraph()
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 2)
				bgp_topology.add_edge(2, 1, type = 2)
				
				## Edge (2,3)		
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
				
				## Edge (1,3)
				bgp_topology.add_edge(1, 3, type = 1)
				bgp_topology.add_edge(3, 1, type = 3)
				
				sim_config = output_configuration(bgp_topology)
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				
				bgp_sim.loadConfig(sim_config)
				
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['2.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['3.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim.run()
				
				# Everybody can reach the child
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(child) is not None)
				
				# Everybody can reach the parent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is not None)
				
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (2,))
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(child).data['best_path'].aspath, (3,))
				self.assertEquals(bgp_sim._router_list['2.1'].loc_rib.search_exact(child).data['best_path'].aspath, (3,))
	
	def testSimpleTriangleWithFailedLink(self):
		
		if active_tests['testSimpleTriangleWithFailedLink']:
			
			print "Running testSimpleTriangleWithFailedLink ..."

			for (a,b) in itertools.permutations([1,2]):
			
				parent = '1.0.0.0/22'
				deaggregated_parent1 = '1.0.2.0/23'
				deaggregated_parent2 = '1.0.1.0/24'
				child = '1.0.0.0/24'
				
				bgp_topology = nx.DiGraph()
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 2)
				bgp_topology.add_edge(2, 1, type = 2)
				
				## Edge (2,3)		
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
				
				## Edge (1,3)
				bgp_topology.add_edge(1, 3, type = 1)
				bgp_topology.add_edge(3, 1, type = 3)
				
				sim_config = output_configuration(bgp_topology)
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				
				bgp_sim.loadConfig(sim_config)
				
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['2.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['3.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(10)), ['2.1', '3.1'], bgp_sim.EVENT_LINK_DOWN))
				#bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(100)), None, bgp_sim.EVENT_SHOW_ALL_RIBS))
				
				bgp_sim.run()
							
				# Everybody can reach the child
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(child) is not None)
				
				# No one can filter anything
				for router_id in bgp_sim._router_list:
					self.assertTrue(len(bgp_sim._router_list[router_id].filtered_prefixes) == 0)
				
				# No one can reach the parent (because of the link failure)
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is None, msg=router_id + " can reach the parent " + str(parent))
				
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(child).data['type'], 1)
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(deaggregated_parent1).data['type'], 2)
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(deaggregated_parent2).data['type'], 2)
				
				self.assertEquals(bgp_sim._router_list['2.1'].loc_rib.search_exact(child).data['type'], 2)
				self.assertEquals(bgp_sim._router_list['2.1'].loc_rib.search_exact(deaggregated_parent1).data['type'], 0)
				self.assertEquals(bgp_sim._router_list['2.1'].loc_rib.search_exact(deaggregated_parent2).data['type'], 0)
				
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(child).data['type'], 0)
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(deaggregated_parent1).data['type'], 3)
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(deaggregated_parent2).data['type'], 3)
				
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(child).data['fwd_neighbors'], set([None]))
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(deaggregated_parent1).data['fwd_neighbors'], set(['1.1']))
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(deaggregated_parent2).data['fwd_neighbors'], set(['1.1']))
				
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(child).data['best_path'].aspath, (3,))
				self.assertEquals(bgp_sim._router_list['2.1'].loc_rib.search_exact(child).data['best_path'].aspath, (1,3,))
				
				for pfx in [deaggregated_parent1, deaggregated_parent2]:
					self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(pfx).data['best_path'].aspath, (2,))

	
	def testSimpleChain(self):
		
		if active_tests['testSimpleChain']:
			
			print "Running testSimpleChain ..."

			for (a,b) in itertools.permutations([1,2]):
			
				parent = '1.0.0.0/22'
				child = '1.0.0.0/24'
				
				bgp_topology = nx.DiGraph()
        		
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 1)
				bgp_topology.add_edge(2, 1, type = 3)
				
				## Edge (2,3)
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
				
				## Edge (3,4)		
				bgp_topology.add_edge(3, 4, type = 1)
				bgp_topology.add_edge(4, 3, type = 3)
					
				sim_config = output_configuration(bgp_topology)
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				
				bgp_sim.loadConfig(sim_config)
				
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['3.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['4.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				#bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(0.9), None, bgp_sim.EVENT_SHOW_ALL_RIBS))
				
				bgp_sim.run()

	def testSimpleChainWithOneASAnnouncingParentChild(self):
		
		if active_tests['testSimpleChainWithOneASAnnouncingParentChild']:
			
			print "Running testSimpleChainWithOneASAnnouncingParentChild ..."
			
			for (a,b) in itertools.permutations([1,2]):
			
				parent = '1.0.0.0/22'
				child = '1.0.0.0/24'
					
				bgp_topology = nx.DiGraph()
        			
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 1)
				bgp_topology.add_edge(2, 1, type = 3)
					
				## Edge (2,3)
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
					
				## Edge (3,4)		
				bgp_topology.add_edge(3, 4, type = 1)
				bgp_topology.add_edge(4, 3, type = 3)
						
				sim_config = output_configuration(bgp_topology)
					
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
					
				bgp_sim.loadConfig(sim_config)
					
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['4.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['4.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				#bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(0.9), None, bgp_sim.EVENT_SHOW_ALL_RIBS))
					
				bgp_sim.run()

		
	def testRouteConsistencyFiltering(self):
		"""Testing DRAGON route consistency filtering on Figure 2 topology"""
		
		if active_tests['testRouteConsistencyFiltering']:
			
			print "Running testRouteConsistencyFiltering ..."
				
			for (a,b) in itertools.permutations([1,2]):
				
				parent = '1.0.0.0/22'
				child = '1.0.0.0/24'
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				bgp_sim.readConfigFile(config_dir + "dragon_fig2.cfg")
				
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['7.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['9.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				#bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(0.24), None, bgp_sim.EVENT_SHOW_ALL_RIBS))
				
				bgp_sim.run()
				
				# Everybody can reach the parent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is not None)
				
				# The parent is never filtered
				for router_id in bgp_sim._router_list:
					self.assertTrue(parent not in bgp_sim._router_list[router_id].filtered_prefixes)
        		
				# These routers filter the child
				for router_id in ['1.1', '2.1', '4.1', '8.1']:
					self.assertTrue(child in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# These routers *DO NOT* filter the child
				for router_id in ['6.1', '7.1', '9.1']:
					self.assertTrue(child not in bgp_sim._router_list[router_id].filtered_prefixes)
        		
				# These routers reach the child via a CUST
				for router_id in ['1.1', '2.1', '4.1', '6.1', '7.1']:
					self.assertEquals(bgp_sim._router_list[router_id].loc_rib.search_exact(child).data['type'], 1)
				
				# These routers stop learning the child route after filtering
				for router_id in ['3.1', '5.1']:
					self.assertEquals(bgp_sim._router_list[router_id].loc_rib.search_exact(child), None)
					
				self.assertEquals(bgp_sim._router_list['8.1'].loc_rib.search_exact(child).data['type'], 3)
				self.assertEquals(bgp_sim._router_list['9.1'].loc_rib.search_exact(child).data['type'], 0)
				
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (3,4,7))
				self.assertEquals(bgp_sim._router_list['2.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (7,))
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (4,7))
				self.assertEquals(bgp_sim._router_list['4.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (7,))
				self.assertEquals(bgp_sim._router_list['5.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (1,3,4,7))
				self.assertEquals(bgp_sim._router_list['6.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (1,3,4,7))
				self.assertEquals(bgp_sim._router_list['7.1'].loc_rib.search_exact(parent).data['best_path'].aspath, ())
				self.assertEquals(bgp_sim._router_list['8.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (5,1,3,4,7))
				self.assertEquals(bgp_sim._router_list['9.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (7,))
				
				self.assertEquals(bgp_sim._router_list['6.1'].loc_rib.search_exact(child).data['best_path'].aspath, (9,))
				self.assertEquals(bgp_sim._router_list['7.1'].loc_rib.search_exact(child).data['best_path'].aspath, (9,))
				self.assertEquals(bgp_sim._router_list['9.1'].loc_rib.search_exact(child).data['best_path'].aspath, ())
	
	def testFwdConsistencyFiltering(self):
		
		"""Testing DRAGON forwarding consistency filtering on Figure 2 topology"""
		
		if active_tests['testFwdConsistencyFiltering']:
			
			print "Running testFwdConsistencyFiltering ..."
				
			for (a,b) in itertools.permutations([1,2]):
				
				parent = '1.0.0.0/22'
				child = '1.0.0.0/24'
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_FWD_CONSISTENCY
				bgp_sim.readConfigFile(config_dir + "dragon_fig2.cfg")
				
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['7.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['9.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim.run()
				
				# Everybody can reach the parent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is not None)
				
				# The parent is never filtered
				for router_id in bgp_sim._router_list:
					self.assertTrue(parent not in bgp_sim._router_list[router_id].filtered_prefixes)
				
				for router_id in ['2.1', '3.1', '4.1', '5.1', '8.1']:
					self.assertTrue(child in bgp_sim._router_list[router_id].filtered_prefixes)
				
				for router_id in ['1.1', '6.1', '7.1', '9.1']:
					self.assertTrue(child not in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# These routers reach the child via a CUST
				for router_id in ['2.1', '4.1', '6.1', '7.1']:
					self.assertEquals(bgp_sim._router_list[router_id].loc_rib.search_exact(child).data['type'], 1)
				
				self.assertEquals(bgp_sim._router_list['1.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (3,4,7))
				self.assertEquals(bgp_sim._router_list['2.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (7,))
				self.assertEquals(bgp_sim._router_list['3.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (4,7))
				self.assertEquals(bgp_sim._router_list['4.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (7,))
				self.assertEquals(bgp_sim._router_list['5.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (1,3,4,7))
				self.assertEquals(bgp_sim._router_list['6.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (1,3,4,7))
				self.assertEquals(bgp_sim._router_list['7.1'].loc_rib.search_exact(parent).data['best_path'].aspath, ())
				self.assertEquals(bgp_sim._router_list['8.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (5,1,3,4,7))
				self.assertEquals(bgp_sim._router_list['9.1'].loc_rib.search_exact(parent).data['best_path'].aspath, (7,))
				
				self.assertEquals(bgp_sim._router_list['6.1'].loc_rib.search_exact(child).data['best_path'].aspath, (9,))
				self.assertEquals(bgp_sim._router_list['7.1'].loc_rib.search_exact(child).data['best_path'].aspath, (9,))
				self.assertEquals(bgp_sim._router_list['9.1'].loc_rib.search_exact(child).data['best_path'].aspath, ())
	
	def testMultipleLevelRouteConsistency(self):
		
		if active_tests['testMultipleLevelRouteConsistency']:
			
			"""Testing DRAGON route consistency filtering on Figure 4 topology with multiple level of prefixes"""
			
			print "Running testMultipleLevelRouteConsistency ..."
				
			for (a,b,c) in itertools.permutations([1,2,3]):
				
				grand_parent = '1.0.0.0/20'
				parent = '1.0.0.0/22'
				child = '1.0.0.0/24'
							
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				bgp_sim.readConfigFile(config_dir + "dragon_fig4.cfg")
			
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['4.1', grand_parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['5.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(c)), ['6.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim.run()
        	
				# Everybody can reach the grandparent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(grand_parent) is not None)
        		
				# cannot even reach the prefix anymore
				for router_id in ['1.1']:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is None)
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None)
				
				# can filter both prefixes
				for router_id in ['3.1']:
					self.assertTrue(parent in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertTrue(child in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# can filter only the child
				for router_id in ['4.1']:
					self.assertTrue(child in bgp_sim._router_list[router_id].filtered_prefixes)
        		
				# can filter only the parent
				for router_id in ['6.1']:
					self.assertTrue(parent in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# can filter nothing
				for router_id in ['5.1']:
					self.assertTrue(grand_parent not in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertTrue(parent not in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertTrue(child not in bgp_sim._router_list[router_id].filtered_prefixes)


	def testMultipleLevelForwardingConsistency(self):
		
		"""Testing DRAGON route consistency filtering on Figure 4 topology with multiple level of prefixes"""
		
		if active_tests['testMultipleLevelForwardingConsistency']:
			
			print "Running testMultipleLevelForwardingConsistency ..."
				
			for (a,b,c) in itertools.permutations([1,2,3]):
				
				grand_parent = '1.0.0.0/20'
				parent = '1.0.0.0/22'
				child = '1.0.0.0/24'
							
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_FWD_CONSISTENCY
				bgp_sim.readConfigFile(config_dir + "dragon_fig4.cfg")
			
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['4.1', grand_parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['5.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(c)), ['6.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim.run()
        	
				# Everybody can reach the grandparent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(grand_parent) is not None)
        		
				# either filter or cannot even reach the prefix anymore
				for router_id in ['1.1', '2.1']:
					self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is None) or \
						 parent in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None) or \
						child in bgp_sim._router_list[router_id].filtered_prefixes)
        	
				for router_id in ['4.1']:
					self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None) or \
						child in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# can only filter q, not p
				for router_id in ['3.1']:
					self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None) or \
						 child in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertFalse((bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is None) or \
						 parent in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# cannot filter
				for router_id in ['5.1']:
					self.assertFalse((bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None) or \
						 child in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertFalse((bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is None) or \
						 parent in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# can only filter p, not q
				for router_id in ['6.1']:
					self.assertFalse((bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None) or \
						 child in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is None) or \
						 parent in bgp_sim._router_list[router_id].filtered_prefixes)
	
	def testMultipleConvergenceEvent(self):
		
		if active_tests['testMultipleConvergenceEvent']:
			
			print "Running testMultipleConvergenceEvent ..."
			
			for (a,b) in itertools.permutations([1,2]):
				
				parent = '10.0.0.0/22'
				deaggregated_prefixes = ['10.0.2.0/23', '10.0.1.0/24']
				child = '10.0.0.0/24'
							
				bgp_topology = nx.DiGraph()
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 2)
				bgp_topology.add_edge(2, 1, type = 2)
				
				## Edge (2,3)		
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
				
				## Edge (1,5)	
				bgp_topology.add_edge(1, 5, type = 1)
				bgp_topology.add_edge(5, 1, type = 3)
				
				## Edge (3,4)
				bgp_topology.add_edge(3, 4, type = 1)
				bgp_topology.add_edge(4, 3, type = 3)
				
				## Edge (4,6)
				bgp_topology.add_edge(4, 6, type = 1)
				bgp_topology.add_edge(6, 4, type = 3)
				
				## Edge (5,6)
				bgp_topology.add_edge(5, 6, type = 1)
				bgp_topology.add_edge(6, 5, type = 3)
				
				## Edge (4,1)
				bgp_topology.add_edge(1, 4, type = 1)
				bgp_topology.add_edge(4, 1, type = 3)
				
				sim_config = output_configuration(bgp_topology)
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				
				bgp_sim.loadConfig(sim_config)
						
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['4.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['6.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(90.00), None, bgp_sim.EVENT_ACTIVATE_DEAGGREGATES))
				
				y = 100.00
				links = [
							('4.1', '6.1'),
							('3.1', '4.1'),
							('2.1', '3.1'),
							('1.1', '2.1'),
							('1.1', '4.1'),
							('1.1', '5.1'),
							('5.1', '6.1')
						]
				i = 2
				while (i>0):
					link_to_fail = random.choice(links)
					bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(y), [link_to_fail[0], link_to_fail[1]], bgp_sim.EVENT_LINK_DOWN))
					bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(y + 200.00), [link_to_fail[0], link_to_fail[1]], bgp_sim.EVENT_LINK_UP))
					y += 200.00
					i -= 1
				bgp_sim.run()
				
				# Everybody can reach the grandparent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is not None)
        		
				# filter the prefix
				for router_id in ['1.1', '3.1']:
					self.assertTrue(child in bgp_sim._router_list[router_id].filtered_prefixes)
				
				for router_id in ['1.1']:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent).data['fwd_neighbors'] == set(['4.1']))
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(child).data['fwd_neighbors'] == set(['4.1', '5.1']))
				
				# Routers 3 and 4 can reach the parent via 1 and 2
				for router_id in ['3.1']:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(child).data['fwd_neighbors'] == set(['4.1']))
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent).data['fwd_neighbors'] == set(['4.1']))

				# become oblivious to the prefix
				for router_id in ['2.1']:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None)
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent).data['fwd_neighbors'] == set(['3.1']))
				
				# cannot filter
				for router_id in ['4.1', '5.1', '6.1']:
					self.assertFalse((bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None) or \
						 child in bgp_sim._router_list[router_id].filtered_prefixes)
					self.assertFalse((bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is None) or \
						 parent in bgp_sim._router_list[router_id].filtered_prefixes)

				for router_id in ['5.1']:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent).data['fwd_neighbors'] == set(['1.1']))
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(child).data['fwd_neighbors'] == set(['6.1']))
				
				for router_id in ['6.1']:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent).data['fwd_neighbors'] == set(['5.1', '4.1']))
	
	def testConvergenceEvent(self):
		
		if active_tests['testConvergenceEvent']:
			
			print "Running testConvergenceEvent ..."
			
			#for (a,b) in itertools.permutations([1,2]):
			for (a,b) in [(1,2)]:
				
				parent = '10.0.0.0/22'
				deaggregated_prefixes = ['10.0.2.0/23', '10.0.1.0/24']
				child = '10.0.0.0/24'
							
				bgp_topology = nx.DiGraph()
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 2)
				bgp_topology.add_edge(2, 1, type = 2)
				
				## Edge (2,3)		
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
				
				## Edge (1,5)	
				bgp_topology.add_edge(1, 5, type = 1)
				bgp_topology.add_edge(5, 1, type = 3)
				
				## Edge (3,4)
				bgp_topology.add_edge(3, 4, type = 1)
				bgp_topology.add_edge(4, 3, type = 3)
				
				## Edge (4,6)
				bgp_topology.add_edge(4, 6, type = 1)
				bgp_topology.add_edge(6, 4, type = 3)
				
				## Edge (5,6)
				bgp_topology.add_edge(5, 6, type = 1)
				bgp_topology.add_edge(6, 5, type = 3)
				
				## Edge (4,1)
				bgp_topology.add_edge(1, 4, type = 1)
				bgp_topology.add_edge(4, 1, type = 3)
				
				sim_config = output_configuration(bgp_topology)
				
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
				
				bgp_sim.loadConfig(sim_config)
						
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['4.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['6.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				#bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(100.00), None, bgp_sim.EVENT_SHOW_ALL_RIBS))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(199.00), None, bgp_sim.EVENT_ACTIVATE_DEAGGREGATES))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(200.00), ['4.1', '6.1'], bgp_sim.EVENT_LINK_DOWN))
				
				bgp_sim.run()
				
				# Everybody can reach the parent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact(parent) is not None)
				
				# 1 cannot filter anything
				self.assertTrue(len(bgp_sim._router_list['1.1'].filtered_prefixes) == 0)
				
				# 1 advertises the parent as aggregate
				self.assertTrue(bgp_sim._router_list['1.1'].aggregated_prefixes == [parent])
				
				# 2, 3, 4 can filter 10.0.0.0/24
				for router_id in ['2.1', '3.1', '4.1']:
					self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(child) is None) or \
					 child in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# 1, 2, 3 reaches the de-aggregates via 4
				for router_id in ['2.1', '3.1']:
					for pfx in deaggregated_prefixes:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx).data['best_path'].aspath[-1] == 4))
				
				# 5 and 6 filter the de-aggregates from 4
				for router_id in ['5.1', '6.1']:
					for pfx in deaggregated_prefixes:
						self.assertTrue((bgp_sim._router_list['5.1'].loc_rib.search_exact(pfx) is None) or \
							pfx in bgp_sim._router_list['5.1'].filtered_prefixes)

	def testConvergenceEventBGPOnly(self):
		
		if active_tests['testConvergenceEventBGPOnly']:
			
			print "Running testConvergenceEventBGPOnly ..."
			
			for (a,b) in itertools.permutations([1,2]):
				
				parent = '10.0.0.0/22'
				child = '10.0.0.0/24'
							
				bgp_topology = nx.DiGraph()
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 2)
				bgp_topology.add_edge(2, 1, type = 2)
				
				## Edge (2,3)		
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
				
				## Edge (1,5)	
				bgp_topology.add_edge(1, 5, type = 1)
				bgp_topology.add_edge(5, 1, type = 3)
				
				## Edge (3,4)
				bgp_topology.add_edge(3, 4, type = 1)
				bgp_topology.add_edge(4, 3, type = 3)
				
				## Edge (4,6)
				bgp_topology.add_edge(4, 6, type = 1)
				bgp_topology.add_edge(6, 4, type = 3)
				
				## Edge (5,6)
				bgp_topology.add_edge(5, 6, type = 1)
				bgp_topology.add_edge(6, 5, type = 3)
				
				## Edge (4,1)
				bgp_topology.add_edge(1, 4, type = 1)
				bgp_topology.add_edge(4, 1, type = 3)
				
				sim_config = output_configuration(bgp_topology)
				
				bgp_sim.init(output="simulation_output")
				bgp_sim.DRAGON_ACTIVATED = False
				
				bgp_sim.loadConfig(sim_config)
						
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['4.1', parent], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['6.1', child], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(9.00), None, bgp_sim.EVENT_RESET_COUNTERS))

				#bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(45.00), None, bgp_sim.EVENT_SHOW_ALL_RIBS))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(60.00), ['5.1', '1.1'], bgp_sim.EVENT_LINK_DOWN))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(90.00), ['5.1', '1.1'], bgp_sim.EVENT_LINK_UP))
				#bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(120.00), ['5.1', '1.1'], bgp_sim.EVENT_SHOW_ALL_RIBS))
				
				bgp_sim.run()				
	
	def testGenerateAggregatesForNonCoveredPrefixes(self):
		
		
		if active_tests['testGenerateAggregatesForNonCoveredPrefixes']:
		
			print "Running testGenerateAggregatesForNonCoveredPrefixes ..."
			
			bgp_sim.RESTRICT_AGGREGATES_TO_PARENTLESS_PREFIXES = False
			
			for (a,b) in itertools.permutations([1,2]):
				
				child1 = '10.0.0.0/24'
				child2 = '10.0.1.0/24'
				
				bgp_topology = nx.DiGraph()
            	
				## Edge (0,1)
				bgp_topology.add_edge(0, 1, type = 1)
				bgp_topology.add_edge(1, 0, type = 3)
		    	
				## Edge (1,3)
				bgp_topology.add_edge(1, 3, type = 1)
				bgp_topology.add_edge(3, 1, type = 3)
		    	
				## Edge (1,4)		
				bgp_topology.add_edge(1, 4, type = 1)
				bgp_topology.add_edge(4, 1, type = 3)
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 1)
				bgp_topology.add_edge(2, 1, type = 3)
		    	
				## Edge (2,3)	
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
		    	
				## Edge (2,4)
				bgp_topology.add_edge(2, 4, type = 1)
				bgp_topology.add_edge(4, 2, type = 3)
					
				sim_config = output_configuration(bgp_topology)
		    	
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
		    	
				bgp_sim.loadConfig(sim_config)
					
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['3.1', child1], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['4.1', child2], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim.run()
				
				# Everybody can reach the parent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact('10.0.0.0/23') is not None)
				
				# Everybody except 2.1 can reach the parent with the 2 routes
				for router_id in set(bgp_sim._router_list) - set(['2.1']):
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact('10.0.0.0/23').data['best_path'].aspath[-1] == 2)
				
				# These guys can filter all the children
				for router_id in ['0.1', '1.1']:
					for pfx in [child1, child2]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# These guys can filter the other childs
				for router_id in ['3.1']:
					for pfx in [child2]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# These guys can filter the other childs
				for router_id in ['4.1']:
					for pfx in [child1]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)

	def testGenerateAggregatesForNonCoveredPrefixesWithFailure(self):
		
		
		if active_tests['testGenerateAggregatesForNonCoveredPrefixesWithFailure']:
		
			print "Running testGenerateAggregatesForNonCoveredPrefixesWithFailure ..."
			
			bgp_sim.RESTRICT_AGGREGATES_TO_PARENTLESS_PREFIXES = False
			
			for (a,b) in itertools.permutations([1,2]):
				
				child1 = '10.0.0.0/24'
				child2 = '10.0.1.0/24'
			
				bgp_topology = nx.DiGraph()
            	
				## Edge (0,1)
				bgp_topology.add_edge(0, 1, type = 1)
				bgp_topology.add_edge(1, 0, type = 3)
		    	
				## Edge (1,3)
				bgp_topology.add_edge(1, 3, type = 1)
				bgp_topology.add_edge(3, 1, type = 3)
		    	
				## Edge (1,4)		
				bgp_topology.add_edge(1, 4, type = 1)
				bgp_topology.add_edge(4, 1, type = 3)
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 1)
				bgp_topology.add_edge(2, 1, type = 3)
		    	
				## Edge (2,3)	
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
		    	
				## Edge (2,4)
				bgp_topology.add_edge(2, 4, type = 1)
				bgp_topology.add_edge(4, 2, type = 3)
					
				sim_config = output_configuration(bgp_topology)
		    	
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
		    	
				bgp_sim.loadConfig(sim_config)
					
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['3.1', child1], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['4.1', child2], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(10)), ['1.1', '2.1'], bgp_sim.EVENT_LINK_DOWN))
				
				bgp_sim.run()
				
				# Everybody can reach the parent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact('10.0.0.0/23') is not None)
				
				# Router 0 can reach the parent via 1
				self.assertTrue(bgp_sim._router_list['0.1'].loc_rib.search_exact('10.0.0.0/23').data['best_path'].aspath[-1] == 1)
            	
				# Routers 3 and 4 can reach the parent via 1 and 2
				for router_id in ['3.1', '4.1']:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact('10.0.0.0/23').data['fwd_neighbors'] == set(['2.1', '1.1']))
				
				# Router 0.1 can filter all the children
				for pfx in [child1, child2]:
					self.assertTrue((bgp_sim._router_list['0.1'].loc_rib.search_exact(pfx) is None) or \
					 pfx in bgp_sim._router_list['0.1'].filtered_prefixes)
				
				# These guys can filter the other childs
				for router_id in ['3.1']:
					for pfx in [child2]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# These guys can filter the other childs
				for router_id in ['4.1']:
					for pfx in [child1]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)

	def testGenerateAggregatesForNonCoveredPrefixesWithFailureAndBack(self):
		
		
		if active_tests['testGenerateAggregatesForNonCoveredPrefixesWithFailureAndBack']:
			
			bgp_sim.RESTRICT_AGGREGATES_TO_PARENTLESS_PREFIXES = False
				
			print "Running testGenerateAggregatesForNonCoveredPrefixesWithFailureAndBack ..."

			for (a,b) in itertools.permutations([1,2]):
				
				child1 = '10.0.0.0/24'
				child2 = '10.0.1.0/24'
		
				bgp_topology = nx.DiGraph()
            	
				## Edge (0,1)
				bgp_topology.add_edge(0, 1, type = 1)
				bgp_topology.add_edge(1, 0, type = 3)
		    	
				## Edge (1,3)
				bgp_topology.add_edge(1, 3, type = 1)
				bgp_topology.add_edge(3, 1, type = 3)
		    	
				## Edge (1,4)		
				bgp_topology.add_edge(1, 4, type = 1)
				bgp_topology.add_edge(4, 1, type = 3)
				
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 1)
				bgp_topology.add_edge(2, 1, type = 3)
		    	
				## Edge (2,3)	
				bgp_topology.add_edge(2, 3, type = 1)
				bgp_topology.add_edge(3, 2, type = 3)
		    	
				## Edge (2,4)
				bgp_topology.add_edge(2, 4, type = 1)
				bgp_topology.add_edge(4, 2, type = 3)
					
				sim_config = output_configuration(bgp_topology)
		    	
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
		    	
				bgp_sim.loadConfig(sim_config)
					
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['3.1', child1], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['4.1', child2], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(10)), ['1.1', '2.1'], bgp_sim.EVENT_LINK_DOWN))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(20)), ['1.1', '2.1'], bgp_sim.EVENT_LINK_UP))
				
				bgp_sim.run()
				
				# Everybody can reach the parent
				for router_id in bgp_sim._router_list:
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact('10.0.0.0/23') is not None)
				
				# Everybody except 2.1 can reach the parent with the 2 routes
				for router_id in set(bgp_sim._router_list) - set(['2.1']):
					self.assertTrue(bgp_sim._router_list[router_id].loc_rib.search_exact('10.0.0.0/23').data['best_path'].aspath[-1] == 2)
				
				# These guys can filter all the children
				for router_id in ['0.1', '1.1']:
					for pfx in [child1, child2]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# These guys can filter the other childs
				for router_id in ['3.1']:
					for pfx in [child2]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
				
				# These guys can filter the other childs
				for router_id in ['4.1']:
					for pfx in [child1]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
	
	
	def testAnycastAnnouncementOfAggregate(self):
		
		if active_tests['testAnycastAnnouncementOfAggregate']:
			
			print "Running testAnycastAnnouncementOfAggregate ..."
			
			bgp_sim.RESTRICT_AGGREGATES_TO_PARENTLESS_PREFIXES = False
			
			for (a,b,c) in itertools.permutations([1,2,3]):
				
				child1 = '10.0.0.0/23'
				child2 = '10.0.2.0/24'
				child3 = '10.0.3.0/24'
			
				bgp_topology = nx.DiGraph()
        		
				## Edge (1,2)
				bgp_topology.add_edge(1, 2, type = 2)
				bgp_topology.add_edge(2, 1, type = 2)
	    		
				## Edge (1,3)
				bgp_topology.add_edge(1, 3, type = 1)
				bgp_topology.add_edge(3, 1, type = 3)
	    		
				## Edge (2,4)		
				bgp_topology.add_edge(2, 4, type = 1)
				bgp_topology.add_edge(4, 2, type = 3)
				
				## Edge (5,3)
				bgp_topology.add_edge(3, 5, type = 1)
				bgp_topology.add_edge(5, 3, type = 3)
				
				## Edge (5,4)
				bgp_topology.add_edge(4, 5, type = 1)
				bgp_topology.add_edge(5, 4, type = 3)
	    		
				## Edge (6,3)
				bgp_topology.add_edge(3, 6, type = 1)
				bgp_topology.add_edge(6, 3, type = 3)
				
				## Edge (6,4)
				bgp_topology.add_edge(4, 6, type = 1)
				bgp_topology.add_edge(6, 4, type = 3)
				
				## Edge (7,3)
				bgp_topology.add_edge(3, 7, type = 1)
				bgp_topology.add_edge(7, 3, type = 3)
				
				## Edge (7,4)
				bgp_topology.add_edge(4, 7, type = 1)
				bgp_topology.add_edge(7, 4, type = 3)
					
				sim_config = output_configuration(bgp_topology)
	    		
				bgp_sim.init()
				bgp_sim.DRAGON_FILTERING_MODE = bgp_sim.DRAGON_ROUTE_CONSISTENCY
	    		
				bgp_sim.loadConfig(sim_config)
					
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(a)), ['5.1', child1], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(b)), ['6.1', child2], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				bgp_sim._event_Scheduler.add(bgp_sim.CEvent(bgp_sim.toSystemTime(float(c)), ['7.1', child3], bgp_sim.EVENT_ANNOUNCE_PREFIX))
				
				bgp_sim.run()
				
				# These guys can filter the other childs
				for router_id in ['1.1', '2.1']:
					for pfx in [child1, child2, child3]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
				
				for router_id in ['5.1']:
					for pfx in [child2, child3]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
            	
				for router_id in ['6.1']:
					for pfx in [child1, child3]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
            	
				for router_id in ['7.1']:
					for pfx in [child1, child2]:
						self.assertTrue((bgp_sim._router_list[router_id].loc_rib.search_exact(pfx) is None) or \
						 pfx in bgp_sim._router_list[router_id].filtered_prefixes)
				
				self.assertTrue(bgp_sim._router_list['3.1'].aggregated_prefixes == ['10.0.0.0/22'])
				self.assertTrue(bgp_sim._router_list['4.1'].aggregated_prefixes == ['10.0.0.0/22'])
			
	def testAggregatesComputation(self):
		
		if active_tests['testAggregatesComputation']:
			
			print "Running testAggregatesComputation ..."
			
			parent = '10.0.0.0/20'
			
			#####
			reachable_children_with_types = [('10.0.0.0/24', 1), ('10.0.1.0/24', 1)]
			(announce2children, announce2peer_prov) = compute_aggregate(parent, reachable_children_with_types)
			self.assertEquals(announce2children, ['10.0.0.0/20'])
			self.assertEquals(announce2peer_prov, ['10.0.0.0/20'])
			
			#####
			reachable_children_with_types = [('10.0.0.0/24', 2), ('10.0.1.0/24', 2)]
			(announce2children, announce2peer_prov) = compute_aggregate(parent, reachable_children_with_types)
			
			self.assertEquals(announce2children, ['10.0.0.0/20'])
			self.assertEquals(sorted(announce2peer_prov), sorted(['10.0.8.0/21', '10.0.4.0/22', '10.0.2.0/23']))
			
			#####
			reachable_children_with_types = [('10.0.0.0/24', 1), ('10.0.1.0/24', 2)]
			(announce2children, announce2peer_prov) = compute_aggregate(parent, reachable_children_with_types)
			self.assertEquals(announce2children, ['10.0.0.0/20'])
			self.assertEquals(sorted(announce2peer_prov), sorted(['10.0.0.0/24', '10.0.8.0/21', '10.0.4.0/22', '10.0.2.0/23']))
			
			#####
			reachable_children_with_types = [('10.0.0.0/24', 1), ('10.0.1.0/24', 3)]
			(announce2children, announce2peer_prov) = compute_aggregate(parent, reachable_children_with_types)
			self.assertEquals(announce2children, ['10.0.0.0/20'])
			self.assertEquals(sorted(announce2peer_prov), sorted(['10.0.0.0/24', '10.0.8.0/21', '10.0.4.0/22', '10.0.2.0/23']))
			
			#####
			reachable_children_with_types = [('10.0.0.0/24', 2), ('10.0.1.0/24', 4)]
			(announce2children, announce2peer_prov) = compute_aggregate(parent, reachable_children_with_types)
			
			self.assertEquals(announce2children, sorted(['10.0.0.0/24', '10.0.8.0/21', '10.0.4.0/22', '10.0.2.0/23']))
			self.assertEquals(sorted(announce2peer_prov), sorted(['10.0.8.0/21', '10.0.4.0/22', '10.0.2.0/23']))
			
			#####
			reachable_children_with_types = [('10.0.0.0/24', 4), ('10.0.1.0/24', 4)]
			(announce2children, announce2peer_prov) = compute_aggregate(parent, reachable_children_with_types)
			self.assertEquals(announce2children, sorted(['10.0.8.0/21', '10.0.4.0/22', '10.0.2.0/23']))
			self.assertEquals(sorted(announce2peer_prov), sorted(['10.0.8.0/21', '10.0.4.0/22', '10.0.2.0/23']))
			
if __name__ == '__main__':
	unittest.main()