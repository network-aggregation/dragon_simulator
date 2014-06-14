#!/usr/bin/env python

import sys
import string
import re
import time
import random
import radix
import networkx
import bz2

from collections import defaultdict
from utils import *
from lib.aggregates import wrapper

MAX_PATH_NUMBER = 1

MRAI_PEER_BASED = 0
MRAI_PREFIX_BASED = 1

MRAI_JITTER = True

bgp_always_compare_med = False
ssld = False
wrate = False

always_mrai = True
default_local_preference = 100

default_weight = 1000

ALTERNATIVE_NONE = 0
ALTERNATIVE_EXIST = 1
ALTERNATIVE_BACKUP = 2

ATTRIBUTE_LOCAL = 0
ATTRIBUTE_CUST = 1
ATTRIBUTE_PEER = 2
ATTRIBUTE_PROV = 3
ATTRIBUTE_UNREACHABLE = 4

RANDOMIZED_KEY = ""

SHOW_UPDATE_RIBS = False
SHOW_RECEIVE_EVENTS = False
SHOW_SEND_EVENTS = False
SHOW_FINAL_RIBS = False
SHOW_DEBUG = False
SHOW_LINK_EVENTS = False
SHOW_ANNOUNCE_EVENTS = False
SHOW_EXPORT_FILTER_EVENTS = False

CHECK_LOOP = False

_link_delay_table = {}
default_link_delay_func = ["uniform", 0.01, 0.1]
default_process_delay_func = ["uniform", 0.001, 0.01]

###################################
#
# DRAGON-related variables
#
# FILTERING_MODE = 1 > Routing consistency
# FILTERING_MODE = 2 > Filtering consistency
#
###################################

DRAGON_ACTIVATED = True
DRAGON_DEBUG = False
DRAGON_ROUTE_CONSISTENCY = 0
DRAGON_FWD_CONSISTENCY = 1
DRAGON_FILTERING_MODE = DRAGON_ROUTE_CONSISTENCY

## DRAGON-behavior tuning knob
RESTRICT_AGGREGATES_TO_PARENTLESS_PREFIXES = True
DISABLE_DEAGGREGATES_ANNOUNCEMENT = True
SKIP_STUB_PROCESSING = True

SHOW_STATISTICS = False

allocated_prefixes = None
router2prefix_mapping = None
pfx2children_mapping = None

CUSTOMER = 1
PEER = 2
PROVIDER = 3

###################################
EVENT_TERMINATE = 0
EVENT_MRAI_EXPIRE_SENDTO = 1
EVENT_UPDATE = 2
EVENT_RECEIVE = 3
EVENT_LINK_DOWN = 4
EVENT_LINK_UP   = 5
EVENT_ANNOUNCE_PREFIX = 6
EVENT_WITHDRAW_PREFIX = 7
EVENT_SHOW_ALL_RIBS = 8
EVENT_RESET_COUNTERS = 9
EVENT_ACTIVATE_DEAGGREGATES = 10
EVENT_OUTPUT_UPDATES = 11
EVENT_ACTIVATE_DEBUG = 12
EVENT_START_TRACK_TIME = 13
EVENT_STOP_TRACK_TIME = 14

IBGP_SESSION = 0
EBGP_SESSION = 1

LINK_DOWN = -1
LINK_UP   = 0

_seq_seed = 0

######################
## Utility functions #
######################

def int_to_GR_type(i):
	if i == 0:
		return "LOCL"
	elif i == 1:
		return "CUST"
	elif i == 2:
		return "PEER"
	elif i == 3:
		return "PROV"
	elif i == 4:
		return "UNREACHABLE"

def formatTime(tm):
	return "{0:2.2f}".format(int(tm/10000)*1.0/100)

def getSystemTimeStr():
	global _systime
	return formatTime(_systime)

def sgn(x):
	if x < 0:
		return -1
	elif x == 0:
		return 0
	else:
		return 1

def interpretDelayfunc(obj, rand_seed, delayfunc):
	global RANDOMIZED_KEY
	if delayfunc[0] == "deterministic":
		return delayfunc[1]
	else:
		if rand_seed is None:
			seed = str(obj) + RANDOMIZED_KEY
			rand_seed = random.Random(seed)
		if delayfunc[0] == "normal": # normal mu sigma
			return rand_seed.gauss(delayfunc[1], delayfunc[2])
		elif delayfunc[0] == "uniform": # uniform a b
			return rand_seed.uniform(delayfunc[1], delayfunc[2])
		elif delayfunc[0] == "exponential": # exponential lambda
			return rand_seed.expovariate(delayfunc[1])
		elif delayfunc[0] == "pareto": # pareto alpha
			return rand_seed.paretovariate(delayfunc[1])
		elif delayfunc[0] == "weibull": # weibull alpha beta
			return rand_seed.weibullvariate(delayfunc[1], delayfunc[2])
		else:
			print "Unsupported distribution", self.delayfunc
			sys.exit(-1)

def toSystemTime(tm):
	return tm*1000000

#
# Increment sequence seed
#
def getSequence():
	global _seq_seed
	_seq_seed = _seq_seed + 1
	return _seq_seed

#
# Represents a BGP Router
#
class CRouter:
	id = None # 4 octect ip address
	asn = None # u_int16_t AS number
	peers = None  # dictionary key: router id
	loc_rib = None # radix tree
	origin_rib = None
	filtered_prefixes = None
	aggregate_tree = None
	aggregated_prefixes = None
	next_idle_time = None # the time to process the next update, guarantee procee in order
	mrai = None
	mrai_setting = None
	route_reflector = None
	rand_seed = None
	announced_prefixes = None
	is_stub = False
	
	### Experiments
	
	## Number of updates
	## key is the peer_id of the neighor I'm sending updates to
	## value is the total number of updates
	num_updates = None

	def __init__(self, a, i):
		global MRAI_PEER_BASED, RANDOMIZED_KEY
		self.id = i
		self.asn = a
		self.peers = {} # rib_ins, rib_outs, mrai_timers
		self.loc_rib = radix.Radix()
		self.filtered_prefixes = set()
		self.aggregate_tree = wrapper.aggregate_tree()
		self.aggregated_prefixes = []
		self.origin_rib = {}
		self.next_idle_time = -1
		self.mrai = {}
		self.mrai_setting = MRAI_PEER_BASED
		self.route_reflector = False
		seed = str(self) + RANDOMIZED_KEY
		self.rand_seed = random.Random(seed)
		self.announced_prefixes  = set()
		self.num_updates = defaultdict(int)

	def __str__(self):
		return str(self.id) + "(" + str(self.asn) + ")"

	def setMRAI(self, pid, prefix):
		return self.setMRAIvalue(pid, prefix, self.peers[pid].mrai_timer())

	def setMRAIvalue(self, pid, prefix, value):
		if value <= 0:
			return -1
		global SHOW_DEBUG, MRAI_PEER_BASED, MRAI_PREFIX_BASED
		if self.mrai_setting == MRAI_PEER_BASED:
			if (not self.mrai.has_key(pid)) or self.mrai[pid] < _systime: # has not been set
				self.mrai[pid] = _systime + value
				if SHOW_DEBUG:
					print str(self), "set MRAI timer for ", pid, "to", self.mrai[pid]
			return self.mrai[pid]
		else: # MRAI_PREFIX_BASED:
			if not self.mrai.has_key(pid):
				self.mrai[pid] = {}
			if (not self.mrai[pid].has_key(perfix)) or self.mrai[pid][prefix] < _systime: # if mrai has not been set yet
				self.mrai[pid][prefix] = _systime + value
				if SHOW_DEBUG:
					print str(self), "set MRAI timer for ", pid, prefix, "to", self.mrai[pid]
			return self.mrai[pid][prefix]
			
    #
    # Set MRAI value to 0
    #
	def resetMRAI(self, pid, prefix):
		global MRAI_PEER_BASED, MRAI_PREFIX_BASED
		if self.mrai_setting == MRAI_PEER_BASED and self.mrai.has_key(pid):
			self.mrai[pid] = 0
				#print str(self), "set mrai timer for ", pid, "to", self.mrai[pid]
		else: # MRAI_PREFIX_BASED:
			if self.mrai.has_key(pid) and self.mrai[pid].has_key(perfix): # if mrai has not been set yet
				self.mrai[pid][prefix] = 0
				#print str(self), "set mrai timer for ", pid, prefix, "to", self.mrai[pid]
    #
    # Return next expiring time, or -1 if timer expired.
    #
	def mraiExpires(self, pid, prefix):
		global MRAI_PEER_BASED, MRAI_PREFIX_BASED
		if self.mrai_setting == MRAI_PEER_BASED:
			if (not self.mrai.has_key(pid)) or self.mrai[pid] < _systime:
				return -1 # expires
			else:
				return self.mrai[pid] # return the expected expiring time
		elif self.mrai_setting ==  MRAI_PERFIX_BASED:
			if (not self.mrai.has_key(pid)) or (not self.mrai[pid].has_key(prefix)) or self.mrai[pid][prefix] < _systime:
				return -1 #expired
			else:
				return self.mrai[pid][prefix] # return the expected expiring time
		else:
			print "Invalid MRAI setting"
			sys.exit(-1)
    #
    # Return the link corresponding to the peer pid
    #
	def getPeerLink(self, pid):
		return getRouterLink(self.id, pid)

    #
    # Checking import filter for peer pid and received path. Return boolean
    #
	def importFilter(self, pid, prefix, path):
		global _route_map_list
		#print "check importFilter", self, pid, prefix, path
		if self.getPeerLink(pid).ibgp_ebgp() == EBGP_SESSION:
			# loop detection
			if self.asn in path.aspath:
				return False
		maps = self.peers[pid].getRouteMapIn()
		for mapname in maps:
			map = _route_map_list[mapname]
			if len(map.action) == 0 and (((not map.permit) and map.isMatch(prefix, path)) or (map.permit and (not map.isMatch(prefix, path)))):
				return False
		return True

    #
    # Build path to import based on filters. Return new path instance.
    #
	def importAction(self, pid, prefix, path):
		global _route_map_list, default_local_preference, _router_list
		newpath = CPath()
		newpath.copy(path)
		if self.getPeerLink(pid).ibgp_ebgp() == EBGP_SESSION:
			newpath.weight = default_weight
			newpath.nexthop = self.peers[pid].id
			newpath.local_pref = default_local_preference
			newpath.igp_cost = 0
			if len(newpath.aspath) == 0 or newpath.aspath[0] != _router_list[pid].asn:
				newpath.aspath = (_router_list[pid].asn,) + newpath.aspath
		else:
			newpath.igp_cost = self.getPeerLink(pid).cost + newpath.igp_cost
			newpath.weight = default_weight
		newpath.src_pid = pid
		maps = self.peers[pid].getRouteMapIn()
		for mapname in maps:
			map = _route_map_list[mapname]
			if map.permit and len(map.action) > 0 and map.isMatch(prefix, newpath):
				newpath = map.performAction(newpath)
		return newpath

    #
    # Check if a path can be exported to a peer: Loop detection & map filtering 
    #
	def exportFilter(self, pid, prefix, path):
		global _router_list, ssld, _route_map_list, SHOW_DEBUG
		if path.src_pid == pid:
			if SHOW_EXPORT_FILTER_EVENTS:
				print "source loop detection fail!"
			return False
		if self.getPeerLink(pid).ibgp_ebgp() == EBGP_SESSION: # ebgp
			# poison reverse
			if len(path.aspath) > 0 and _router_list[pid].asn == path.aspath[0]:
				if SHOW_EXPORT_FILTER_EVENTS:
					print "AS path loop detection fail!"
				return False
			# send-side loop detection, SSLD
			if ssld and _router_list[pid].asn in path.aspath:
				if SHOW_EXPORT_FILTER_EVENTS:
					print "AS path ssld loop detection fail!"
				return False
		else: #ibgp
			if (path.src_pid is not None) and self.getPeerLink(path.src_pid).ibgp_ebgp() == IBGP_SESSION:
				#if SHOW_DEBUG:
				#	print "IBGPXXXXX:", str(self), path.src_pid, self.peers[path.src_pid].route_reflector_client, pid, self.peers[pid].route_reflector_client
				if (not self.route_reflector) or ((not self.peers[path.src_pid].route_reflector_client) and (not self.peers[pid].route_reflector_client)):
					if SHOW_EXPORT_FILTER_EVENTS:
						print "IBGPXXXXX:", str(self), path.src_pid, self.peers[path.src_pid].route_reflector_client, pid, self.peers[pid].route_reflector_client, "ibgp route-refelctor checking fail!"
					return False

		#Route maps application
		maps = self.peers[pid].getRouteMapOut()
		for mapname in maps:
			map = _route_map_list[mapname]
			if len(map.action) == 0 and (((not map.permit) and map.isMatch(prefix, path)) or (map.permit and (not map.isMatch(prefix, path)))):
				if SHOW_EXPORT_FILTER_EVENTS:
					print "route map fail!"
				return False
		return True

    #
    # Build path to export based on map actions. Returns a new path with updated attributes.
    #
	def exportAction(self, pid, prefix, path):
		global _route_map_list, EPIC, _systime
		newpath = CPath()
		newpath.copy(path)
		if self.peers[pid].link.ibgp_ebgp() == EBGP_SESSION:
			newpath.local_pref = -1
			newpath.aspath = (self.asn,) + newpath.aspath # append paths
			newpath.igp_cost = -1
		maps = self.peers[pid].getRouteMapOut()
		for mapname in maps:
			map = _route_map_list[mapname]
			if map.permit and len(map.action) > 0 and map.isMatch(prefix, newpath):
				path = map.performAction(newpath)
		return newpath

    #
    # Compare two paths
    #
	def comparePath(self, path1, path2):
		return path1.compareTo(path2)
	
	def get_customers(self):
		return [peer for peer in self.peers if self.peers[peer].peer_type == CUSTOMER]
	
	def get_peer_provs(self):
		return [peer for peer in self.peers if (self.peers[peer].peer_type == PEER or self.peers[peer].peer_type == PROVIDER)]

	## DRAGON CR/CF code
	def dragon_check_filtering(self, node):
		global DRAGON_DEBUG, DRAGON_FILTERING_MODE, DRAGON_ROUTE_CONSISTENCY, DRAGON_FWD_CONSISTENCY
		
		parent_node = node.parent()
		
		if parent_node:
			node_type = node.data['type']
			node_fwd_neighbors = node.data['fwd_neighbors']
			
			parent_type = parent_node.data['type']
			parent_fwd_neighbors = parent_node.data['fwd_neighbors']
			
			if DRAGON_DEBUG:
				print getSystemTimeStr() + " %s DRAGON. Comparing (pfx:%s type:%d fwd_neighbors:%s) and (pfx:%s type:%d fwd_neighbors:%s)" % \
					(self.id, node.prefix, node_type, node_fwd_neighbors, parent_node.prefix, parent_type, parent_fwd_neighbors)
		
			if (DRAGON_FILTERING_MODE == DRAGON_ROUTE_CONSISTENCY):
				# Code CR:
				# If the node is not the destination for p
				# and the elected q-route is as good as
				# or worse than the elected p-route,
				# then filter q-routes.
				if (not parent_node.prefix in self.origin_rib and node_type >= parent_type):
					if DRAGON_DEBUG:
						print "%s %s DRAGON. (%s, %s) is of type RF. Filter." % \
							(getSystemTimeStr(), self.id, node.prefix, parent_node.prefix)
					return True
				else:
					if DRAGON_DEBUG:						
						if parent_node.prefix in self.origin_rib:
							print "%s %s DRAGON. Cannot filter (%s, %s) as I'm originating the parent" % \
								(getSystemTimeStr(), self.id, node.prefix, parent_node.prefix)
						elif node_type < parent_type:
							print "%s %s DRAGON. Cannot filter (%s, %s) as the child type (%d) is strictly better than the parent (%d)." % \
								(getSystemTimeStr(), self.id, node.prefix, parent_node.prefix, node_type, parent_type)
			else:
				# Code CF: 
				# 1. If the elected q-route is worse than the elected p-route, or it is as good as 
				#    the elected p-route and every forwarding neighbor for q is also a forwarding neighbor for p,
				#    then filter q-routes.
				# 2. If the elected q-route is as good as the elected p-route and there is a forwarding neighbor
				#    for q that is not a forwarding neighbor for p, then add the forwarding neighbors for p
				#    to the forwarding-table entry for q and do not export q-routes.
				if (not parent_node.prefix in self.origin_rib and ((node_type > parent_type) or
					(node_type == parent_type and (node_fwd_neighbors.issubset(parent_fwd_neighbors))))):
						if DRAGON_DEBUG:
							print "%s %s DRAGON. (%s, %s) is of type RF. Filter." %\
								(getSystemTimeStr(), self.id, node.prefix, parent_node.prefix)
						return True
				elif ((not parent_node.prefix in self.origin_rib) and (node_type == parent_type) and
					not node_fwd_neighbors.issubset(parent_fwd_neighbors)):
					node.data['fwd_neighbors'] = node.data['fwd_neighbors'].union(parent_node.data['fwd_neighbors'])
					if DRAGON_DEBUG:
						print "%s %s DRAGON. (%s, %s) is of type RX. Do not filter." %\
							(getSystemTimeStr(), self.id, node.prefix, parent_node.prefix)
					return False
		return False
	
	## DRAGON filtering code
	def dragon_start_filtering(self, prefix):
		global DRAGON_DEBUG, _event_Scheduler
		
		if prefix not in self.filtered_prefixes:
			if DRAGON_DEBUG:
				print "%s %s DRAGON. Starts filtering prefix %s." %\
					(getSystemTimeStr(), self.id, prefix)
			
			self.filtered_prefixes.add(prefix)
			withdraw_update = CUpdate(prefix)
			# I need to maintain the prefix in my RIB. But I send a WITHDRAW to my neighbors.
			for peer in self.peers.values():
				if prefix in peer.rib_out:
					del peer.rib_out[prefix]
					if DRAGON_DEBUG:
						print "%s %s DRAGON. I filter so send WITHDRAW for prefix %s to %s" %\
							 (getSystemTimeStr(), self.id, prefix, peer.id)
					# If there was an UPDATE enqueued, I need to remove it...
					if DRAGON_DEBUG:
						print "%s %s DRAGON. Dequeuing potential enqueued UPDATEs for prefix %s to peer %s" %\
							 (getSystemTimeStr(), self.id, prefix, peer.id)
					peer.dequeue(prefix)
					_event_Scheduler.add(CEvent(self.getPeerLink(peer.id).next_delivery_time(self.id, withdraw_update.size()),\
						 [self.id, peer.id, withdraw_update], EVENT_RECEIVE))
				else:
					if DRAGON_DEBUG:
						print "%s %s DRAGON. I filter prefix %s but don't send a WITHDRAW to %s. But I dequeue, just in case..." %\
							 (getSystemTimeStr(), self.id, prefix, peer.id)
					peer.dequeue(prefix)
		else:
			if DRAGON_DEBUG:
				print "%s %s DRAGON. Asked to filter prefix %s which is already filtered." %\
				(getSystemTimeStr(), self.id, prefix)

	def dragon_stop_filtering(self, prefix):
		if prefix in self.filtered_prefixes:
			if DRAGON_DEBUG:
				print "%s %s DRAGON. Stops filtering prefix %s." %\
					(getSystemTimeStr(), self.id, prefix)
			self.filtered_prefixes.remove(prefix)
			
			# I need to send to my peer my best path again for this prefix, take into account the MRAI!
			for pid in self.peers:
				self.presend2peer(pid, prefix)

    # BGP selection process. Return change in best path and changing trend.
    #   Change = true if best path (or any path in the loc_rib) changed.
	#   Trend = +1 if new best path is better than old one, -1 if the old one was better.
	def pathSelection(self, prefix):
		
		inpaths = []
		change = False
		trend = 0
		replace_local_aggregate = False
		
		###  I'm eligible to advertise an aggregate, and I received a route
		###  via a customer. But now I've lost it because of a WITHDRAW. 
		###  I need to re-advertise the aggregate.
		
		if DRAGON_ACTIVATED:
		    # prefix not in self.aggregated_prefixes
		    if self.origin_rib.has_key(prefix) and (prefix not in self.aggregated_prefixes):
		    	inpaths.append(self.origin_rib[prefix])
		    else:
		    	if prefix in self.aggregated_prefixes:
		    		inpaths.append(self.origin_rib[prefix])
		    	for peer in self.peers.values():
		    		if peer.rib_in.has_key(prefix):
		    			for path in peer.rib_in[prefix]:
		    				inpaths.append(path)
		    	inpaths.sort(self.comparePath)
		else:
		    if self.origin_rib.has_key(prefix):
		    	inpaths.append(self.origin_rib[prefix])
		    else:
		    	for peer in self.peers.values():
		    		if peer.rib_in.has_key(prefix):
		    			for path in peer.rib_in[prefix]:
		    				inpaths.append(path)
		    	inpaths.sort(self.comparePath)
		
		if DRAGON_DEBUG:
			print "%s %s Running Decision Process for prefix %s with inpaths: %s" %\
				(getSystemTimeStr(), self.id, prefix, inpaths)
		
		node = self.loc_rib.search_exact(prefix)
		
		if node is None:
			if inpaths:
				node = self.loc_rib.add(prefix)
				node.data['type'] = ATTRIBUTE_UNREACHABLE
				node.data['fwd_neighbors'] = set()
				node.data['best_path'] = None
			else:
				# no current node known and no new node has well
				return [change, trend, node, replace_local_aggregate]
		
		if not node.data['best_path'] and inpaths:
			node.data['type'] = int(inpaths[0].community[0])
			node.data['fwd_neighbors'] = set([path.src_pid for path in inpaths if\
				 int(path.community[0]) == node.data['type']])
			node.data['best_path'] = inpaths[0]
			trend = 1
			change = True
		elif node.data['best_path'] and not inpaths:
			# router is not able to reach 'prefix' anymore
			self.loc_rib.delete(prefix)
			node = None
			trend = -1;
			change = True;
		elif node.data['best_path'] and inpaths:
			if prefix in self.aggregated_prefixes and DRAGON_ACTIVATED:
				## I'm advertising an aggregate, but now I've received a route via a customer. So, I can stop advertising the former.
				if len(inpaths) > 1:
					if int(inpaths[1].community[0]) == 1:
						node.data['type'] = 1
						node.data['best_path'] = inpaths[1]
						node.data['fwd_neighbors'] = set([path.src_pid for path in inpaths if\
							int(path.community[0]) == node.data['type']])
						change = True
						trend = 1
						replace_local_aggregate = True
						self.aggregated_prefixes.remove(prefix)
						del self.origin_rib[prefix]
						if DRAGON_DEBUG:
							print "%s %s DRAGON. I've learned a customer route to the aggregate %s I was generating... Best route is now: %s" %\
								(getSystemTimeStr(), self.id, prefix, inpaths[1])
					else:
						## I'm advertisting an aggregate, and I've received
						## a route via a peer or a provider. I continue
						## advertising my route, or it turns out that I was not
						## the first to advertise the route ... in which case
						## I've to start advertising it here!
						node.data['type'] = int(inpaths[0].community[0])
						node.data['fwd_neighbors'] = set([path.src_pid for path in inpaths if\
							 int(path.community[0]) == node.data['type']])
						node.data['best_path'] = inpaths[0]
						trend = 1
						change = True
				else:
					## There is only one path in inpaths...
					node.data['type'] = int(inpaths[0].community[0])
					node.data['fwd_neighbors'] = set([path.src_pid for path in inpaths if\
						 int(path.community[0]) == node.data['type']])
					node.data['best_path'] = inpaths[0]
					trend = 1
					change = True
			else:		
				trend = node.data['best_path'].compareTo(inpaths[0])
				old_best_path = node.data['best_path']
				node.data['type'] = int(inpaths[0].community[0])
				node.data['best_path'] = inpaths[0]
				node.data['fwd_neighbors'] = set([path.src_pid for path in inpaths if\
					int(path.community[0]) == node.data['type']])
				change = (old_best_path != node.data['best_path'])
			
		return [change, trend, node, replace_local_aggregate]

    #
    # Receive an UPDATE: put paths in adj_rib_in and schedule BGP Decision Process
    #
	def receive(self, pid, update):
		#Link is down, update is invalid => discard
		if self.getPeerLink(pid).status == LINK_DOWN:
			return
		tmppaths = []
		for path in update.paths:
			#Run import filters on received paths, then create new path entry with filter action applied
			if self.importFilter(pid, update.prefix, path):
				tmppaths.append(self.importAction(pid, update.prefix, path))
		
		if tmppaths:
			#Replace adjribin entry with new paths.
			self.peers[pid].rib_in[update.prefix] = tmppaths
		else:
			self.peers[pid].rib_in.pop(update.prefix, None)
				
		#Schedule next event : rerun decision process for this prefix after processing delay
		_event_Scheduler.add(CEvent(self.getIdelTime(), [self.id, update.prefix], EVENT_UPDATE))

    #
    # Update routing tables to remove entries from down peer
    #
	def peerDown(self, pid):
		if SHOW_DEBUG:
			print "peerDown", str(self), pid
		prefixlist = self.peers[pid].rib_in.keys()
		self.peers[pid].clear()
		#Rerun decision process for each prefix whose nexthop is the failed peer
		for p in prefixlist:
			if SHOW_DEBUG:
				print getSystemTimeStr() + " %s Re-running the Decision Process for prefix %s" % (self.id, p)
			self.update(p)

	def peerUp(self, pid):
		if SHOW_DEBUG:
			print "peerUp", str(self), pid
		#Set up MRAI and send routing table to new peer
		if self.mrai_setting == MRAI_PEER_BASED:
			for p in self.loc_rib.prefixes():
				if p not in self.filtered_prefixes or not DRAGON_ACTIVATED:
					self.peers[pid].enqueue(p)
			next_mrai = self.mraiExpires(pid, None)
			if next_mrai < 0:
				self.sendto(pid, None)
		else:
			for p in self.loc_rib.prefixes():
				if p not in self.filtered_prefixes or not DRAGON_ACTIVATED:
					self.peer[pid].enqueue(p)
					next_mrai = self.mraiExpires(pid, p)
					if next_mrai < 0:
						self.sendto(pid, p)
	
	def compute_local_aggregates(self):
		
		new_aggregates = wrapper.get_aggregates_pfxes(self.aggregate_tree)
		
		if RESTRICT_AGGREGATES_TO_PARENTLESS_PREFIXES:
			new_aggregates = list(set(new_aggregates).intersection(set(parentless_prefixes)))
			if DRAGON_DEBUG:
				print "%s %s DRAGON. Restricted aggregates: %s" %\
					(getSystemTimeStr(), self.id, new_aggregates)
		
		delta_aggregates = compute_delta_between_prefix_list(self.aggregated_prefixes, new_aggregates)
		
		if DRAGON_DEBUG:
			if self.aggregated_prefixes or new_aggregates or delta_aggregates:
				print "%s %s DRAGON. Aggregates\n\t old: %s\n\t new:%s\n\t delta:%s" % \
					(getSystemTimeStr(), self.id, self.aggregated_prefixes, new_aggregates, delta_aggregates)
			else:
				print "%s %s DRAGON. No aggregate to advertise..." % \
					(getSystemTimeStr(), self.id)
		self.aggregated_prefixes = new_aggregates
				
		for (pfx, announce) in sorted(delta_aggregates, key=lambda tup: tup[1], reverse=False):
			if not announce:
				if DRAGON_DEBUG:
					print "%s %s DRAGON. WITHDRAWING aggregate: %s" % (getSystemTimeStr(), self.id, pfx)
				self.withdraw_prefix(pfx)
			else:
				if DRAGON_DEBUG:
					print "%s %s DRAGON. Announcing aggregate: %s" % (getSystemTimeStr(), self.id, pfx)
				self.announce_prefix(pfx)
	
	def compute_local_announcements(self, prefix):
		
		## if prefix is a child of another locally originated prefix
		## advertise it. It will be filtered directly anyway (by all the upstreams)
		is_child = False
		for locally_originated_prefix in router2prefix_mapping[self.id]:
			if (prefix != locally_originated_prefix) and (IPv4Network(prefix) in IPv4Network(locally_originated_prefix)):
				is_child = True
		if is_child:
			self.announce_prefix(prefix)
		else:
			reachable_children_and_types = []
			
			delegated_children = {}
			for child in pfx2children_mapping[IPv4Network(prefix)]:
				if str(child) in router2prefix_mapping[self.id]:
					reachable_children_and_types.append((child, ATTRIBUTE_LOCAL))
				else:
					if DISABLE_DEAGGREGATES_ANNOUNCEMENT:
						reachable_children_and_types.append((child, 1))
						delegated_children[child] = True						
					else:
						node = self.loc_rib.search_exact(str(child))
						if not node:
							reachable_children_and_types.append((child, ATTRIBUTE_UNREACHABLE))
						else:
							reachable_children_and_types.append((child, node.data['type']))
							if node.data['type'] != 0:
								delegated_children[child] = True
			
			new_announcements = compute_aggregate(prefix, reachable_children_and_types)
			delta_prefixes = compute_delta_between_prefix_list(self.announced_prefixes, new_announcements)
			self.announced_prefixes = new_announcements
			
			#if DRAGON_DEBUG:
			#	print "%s %s DRAGON, delta_prefixes: %s, delegated_children: %s" % (getSystemTimeStr(), self.id, delta_prefixes, delegated_children)
			
			for (pfx, announce) in sorted(delta_prefixes, key=lambda tup: tup[1], reverse=False):
				if pfx not in delegated_children:
					if announce:
						self.announce_prefix(pfx)
					else:
						self.withdraw_prefix(pfx)

	def update_local(self, prefix):
		for parent_pfx in router2prefix_mapping[self.id]:
			if IPv4Network(prefix) in IPv4Network(parent_pfx):
				if DRAGON_DEBUG:
					print "%s %s DRAGON. Recompute local announcements as prefix %s is a child of one of my prefixes: (%s)" %\
						 (getSystemTimeStr(), self.id, prefix, parent_pfx)
				self.compute_local_announcements(parent_pfx)
	
	def update(self, prefix):
		global SHOW_UPDATE_RIBS, CHECK_LOOP, SHOW_DEBUG, DRAGON_DEBUG, DRAGON_ACTIVATED
		
		cur_node = self.loc_rib.search_exact(prefix)
		
		cur_type = None
		cur_neighbors = None
		cur_children = None
		
		if cur_node:
			cur_type = cur_node.data['type']
			cur_neighbors = cur_node.data['fwd_neighbors'].copy()
			cur_children = cur_node.children()[:]
		
		[change, trend, new_node, replace_local_aggregate] = self.pathSelection(prefix)
		
		if DRAGON_ACTIVATED and prefix not in self.origin_rib:
			if DRAGON_DEBUG:
				print "%s %s Decision Process outcome for prefix %s:\n\t -change:%s\n\t -previous_best: %s\n\t -cur_best: %s"\
					% (getSystemTimeStr(), self.id, prefix, change, ("type:", cur_type, "fwd_neighbors:", cur_neighbors) if cur_node else None,\
						 ("type:", new_node.data['type'], "fwd_neighbors:", new_node.data['fwd_neighbors']) if new_node else None)
			
			recompute_aggregates = True
			if not self.is_stub:
				for parent_pfx in router2prefix_mapping[self.id]:
					if IPv4Network(prefix) in IPv4Network(parent_pfx):
						recompute_aggregates = False
						break
							
			if (((not cur_node and new_node) and new_node.data['best_path']) or \
				(cur_node and new_node and cur_type != new_node.data['type']) or \
				(cur_node and new_node and cur_neighbors != new_node.data['fwd_neighbors'])):

				## There was a Path UPDATE
				if DRAGON_DEBUG:
					print "%s %s Running DRAGON for prefix %s (Reason: best path change)"\
						% (getSystemTimeStr(), self.id, prefix)
				
				if not self.is_stub:
					if prefix not in self.origin_rib:
						insert = True
						for parent_pfx in router2prefix_mapping[self.id]:
							if IPv4Network(prefix) in IPv4Network(parent_pfx):
								insert = False
								break
						if insert:
							recompute_aggregates = True
							wrapper.insert_pfx(self.aggregate_tree, str(prefix), new_node.data['type'])

				# First, check whether the current node can be
				# filtered wrt its direct parent
				if self.dragon_check_filtering(new_node):
					self.dragon_start_filtering(prefix)
				else:
					## If the prefix was filtered
					## Stop considering it filtered
					self.dragon_stop_filtering(prefix)
					
					# Second, check whether the children of the 
					# current node can be filtered
					for child in new_node.children():
						if DRAGON_DEBUG:
							print "%s %s Running DRAGON on the child of prefix %s (%s) for which there was a change of best path." % \
							 (getSystemTimeStr(), self.id, prefix, child.prefix)
						if self.dragon_check_filtering(child):
							self.dragon_start_filtering(child.prefix)
						else:
							## If the prefix was filtered
							## Stop considering it filtered
							self.dragon_stop_filtering(child.prefix)
				
			elif cur_node and cur_node.data['best_path'] and not new_node:

				## I'm not able to reach the path anymore
				if DRAGON_DEBUG:
					print "%s %s Running DRAGON for prefix %s (Reason: reachability lost)"\
						% (getSystemTimeStr(), self.id, prefix)
				
				if not self.is_stub:
					if prefix not in self.origin_rib:
						insert = True
						for parent_pfx in router2prefix_mapping[self.id]:
							if IPv4Network(prefix) in IPv4Network(parent_pfx):
								insert = False
								break
						if insert:
							recompute_aggregates = True
							wrapper.insert_pfx(self.aggregate_tree, str(prefix), 4)
				
				## If the prefix was filtered
				## Stop considering it filtered
				self.dragon_stop_filtering(prefix)

				for child in cur_children:		
					## These prefixes might still be filtered based on my parent
					if self.dragon_check_filtering(child):
						if child.prefix not in self.filtered_prefixes:
							if DRAGON_DEBUG:
								print "%s %s prefix %s was NOT filtered before but now it can because %s is not reachable anymore."\
									% (getSystemTimeStr(), self.id, child.prefix, prefix)
							self.dragon_start_filtering(child.prefix)
					else:
						# we cannot filter the child
						if DRAGON_DEBUG:
							print "%s %s DRAGON. prefix %s CANNOT be filtered. Filtered prefixes: %s" % (getSystemTimeStr(), self.id, child.prefix, self.filtered_prefixes)
						if child.prefix in self.filtered_prefixes:
							if DRAGON_DEBUG:
								print "%s %s DRAGON. prefix %s was filtered before but CANNOT anymore because %s is not reachable anymore."\
								% (getSystemTimeStr(), self.id, child.prefix, prefix)
							self.dragon_stop_filtering(child.prefix)
			
			else:
				if DRAGON_DEBUG:
					print "%s %s DRAGON. Nothing to do for %s. The paths are unchanged." % (getSystemTimeStr(), self.id, prefix)
			
		if SHOW_UPDATE_RIBS:
			self.showRib(prefix)

		# best path(s) changed: send new best path(s) to peers
		if change:
			if prefix not in self.filtered_prefixes:
				for pid in self.peers:
					self.presend2peer(pid, prefix)
				
				if CHECK_LOOP:
					forwardingCheck(self, prefix)
			else:
				if DRAGON_DEBUG:
					print "%s %s DRAGON. Not propagating UPDATE for prefix %s as it is filtered." %\
						(getSystemTimeStr(), self.id, prefix)
			
			if DRAGON_ACTIVATED and prefix not in self.origin_rib:
				# update local announcements
				if prefix not in self.origin_rib:
					self.update_local(prefix)
				
				# update aggregates announcement
				if (not self.is_stub) and recompute_aggregates and not replace_local_aggregate:
					if DRAGON_DEBUG:
						print "%s %s DRAGON. Recomputing aggregates prefixes, now considering %s." %\
						 (getSystemTimeStr(), self.id, prefix)
					self.compute_local_aggregates()
	
	def showRib(self, prefix):
		tmpstr = getSystemTimeStr() + " RIB: " + str(self) + "*" + prefix
		node = self.loc_rib.search_exact(prefix)
		if node:
			type_ = node.data['type']
			forwarding_neighbors = node.data['fwd_neighbors']
			best_path = node.data['best_path']
			
			if not prefix in self.filtered_prefixes:
				tmpstr += "{"
				tmpstr += "*>" + str(prefix) + ' type:' + int_to_GR_type(type_) + ' #fwd_neighbors:' + str(len(forwarding_neighbors)) + ' neighbors:' + str(forwarding_neighbors) + ' best:' + str(best_path)
				tmpstr += "}"
			else:
				tmpstr += "{"
				tmpstr += "*>" + str(prefix) + '[FILTERED]' + ' type:' + int_to_GR_type(type_) + ' #fwd_neighbors:' + str(len(forwarding_neighbors)) + ' neighbors:' + str(forwarding_neighbors) + ' best:' + str(best_path)
				tmpstr += "}"
		print tmpstr

	def showAllRib(self):
		print "Router: %s. Prefixes length: %d" % (self.id, len(self.loc_rib.prefixes()))
		for p in self.loc_rib.prefixes():
			self.showRib(p)

    #
    # Add to peer out_queue and check MRAI
    #
	def presend2peer(self, pid, prefix):
		global wrate, MRAI_PEER_BASED, LINK_DOWN, EVENT_MRAI_EXPIRE_SENDTO, SHOW_DEBUG
		# if the peer is down, we don't send anything to the guy
		if self.getPeerLink(pid).status == LINK_DOWN:
			return
		#add to peer waiting queue
		self.peers[pid].enqueue(prefix)
		#print self, "enqueue", pid, prefix
		
		#Compute sending time
		next_mrai = self.mraiExpires(pid, prefix)
		if next_mrai < 0 and always_mrai:	# Need to reschedule msg sending
			if self.mrai_setting == MRAI_PEER_BASED:
				tprefix = None
			next_mrai = self.setMRAIvalue(pid, tprefix, self.peers[pid].random_mrai_wait())
			if next_mrai > 0:
				_event_Scheduler.add(CEvent(next_mrai, [self.id, pid, tprefix], EVENT_MRAI_EXPIRE_SENDTO))
		
		#If withdraw or if MRAI expired  Send immediately
		if next_mrai < 0:# or self.isWithdrawal(pid, prefix):
			if SHOW_DEBUG:
				if not self.isWithdrawal(pid, prefix):
					print getSystemTimeStr(), self, pid, prefix, " MRAI expires, send immediately ...", pid
				else:
					print getSystemTimeStr(), self, pid, prefix, " Sending WITHDRAW immediately ...", pid
			self.sendto(pid, prefix)
		else: #do nothing, the scheduler will call sendto automatically when mrai timer expires
			if SHOW_DEBUG:
				print getSystemTimeStr(), self, pid, prefix, " MRAI does not expire, wait...", formatTime(next_mrai - _systime)
    
	#
    # Add locally originated prefix, and rerun decision process
    #
	def announce_prefix(self, prefix):
		global default_local_preference
		if SHOW_ANNOUNCE_EVENTS:
			print "%s %s Announcing prefix %s" %\
				(getSystemTimeStr(), self.id, prefix)
		npath = CPath()
		npath.nexthop = self.id
		npath.local_pref = default_local_preference
		npath.community = [ATTRIBUTE_LOCAL]
		self.origin_rib[prefix] = npath
		self.update(prefix)

	#
	# Remove prefix from origin rib and rerun decision process
	#
	def withdraw_prefix(self, prefix):
		if prefix in self.origin_rib:
			del self.origin_rib[prefix]
			self.update(prefix)

	#
	# MRAI expired => send update messages to peer pid
	#
	def sendto(self, pid, prefix): # from out_queue
		global _event_Scheduler, SHOW_SEND_EVENTS

		sendsth = False
		peer = self.peers[pid]
		sendWithdraw = True
		if len(peer.out_queue) > 0:
			i = 0
			#Traverse out_queue
			while i < len(peer.out_queue):
				if prefix is None:  #No prefix specified, MRAI peer based => send msg
					if self.sendtopeer(pid, peer.out_queue[i]):
						sendsth = True
					if not self.isWithdrawal(pid, peer.out_queue[i]):
						sendWithdraw = False
					peer.out_queue.pop(i)
				elif prefix == peer.out_queue[i]: #Prefix in outqueue correspond => send msg
					if self.sendtopeer(pid, peer.out_queue[i]):
						sendsth = True
					if not self.isWithdrawal(pid, peer.out_queue[i]):
						sendWithdraw = False
					peer.out_queue.pop(i)
					break
				else: #Skip, prefix is not the one that was specified
					i = i + 1
		if sendsth: #Reset MRAI
			#if SHOW_SEND_EVENTS:
			#	print getSystemTimeStr(), "EVENT_SENDTO", self, "send", prefix, "to", pid
			if (not wrate) and sendWithdraw:
				return
			#Reset MRAI for this peer or this prefix, depending on config
			if self.mrai_setting == MRAI_PEER_BASED:
				prefix = None
			#self.resetMRAI(pid, prefix)
			next_mrai = self.setMRAI(pid, prefix)
			if next_mrai > 0: 
				_event_Scheduler.add(CEvent(next_mrai, [self.id, pid, prefix], EVENT_MRAI_EXPIRE_SENDTO))
				#print "Add EVENT_MRAI_EXPIRE_SENDTO ", str(self), pid, prefix, next_mrai
		#else:
		#	self.resetMRAI(pid, prefix)
		#	print str(self) + " send nothing to " + pid


    # Check if msg to send to peer pid is a withdraw, i.e.: 
    #	- No best path
    #	- or path filtered by route map
	def isWithdrawal(self, pid, prefix):
		node = self.loc_rib.search_exact(prefix)
		if not node or not node.data['best_path']:
			return True
		send_path = False
		if self.exportFilter(pid, prefix, node.data['best_path']):
			send_path = True
		return not send_path

    # Delivery of an update to a peer if there is a change compared to the ribout
    # BGP Normal or eBGP only
	def delivery(self, pid, prefix, update):
		global _event_Scheduler
		change = False
		if prefix in self.peers[pid].rib_out and len(self.peers[pid].rib_out[prefix])!=0:
			if len(update.paths) > 0:
				if update.paths[0].compareTo2(self.peers[pid].rib_out[prefix][0]) != 0:
					change = True
			else: # Update is a WITHDRAW
				change = True
		#Ribout is empty and all paths have been filtered: Do not send empty update
		elif (not prefix in self.peers[pid].rib_out or len(self.peers[pid].rib_out[prefix])==0) and len(update.paths)==0:
			change = False
		else: #Ribout empty and one path to send
			change = True
		if change:
			self.peers[pid].rib_out[prefix] = update.paths
			
			if SHOW_SEND_EVENTS:
				if len(update.paths) == 0:
					print getSystemTimeStr(), "EVENT_SENDTO", self, "send", prefix, "(W) to", pid
				else:
					print getSystemTimeStr(), "EVENT_SENDTO", self, "send", prefix, " to", pid, " with path:", update.paths
			##
			## Statistics
			##
			if (not DRAGON_ACTIVATED) and pfx_to_multiplicator_map:
				if DRAGON_DEBUG:
					print "Accounting for %d UPDATEs in Statistics" % (pfx_to_multiplicator_map[prefix])
				self.num_updates[pid] += pfx_to_multiplicator_map[prefix]
			else:
				self.num_updates[pid] += 1
			
			if SKIP_STUB_PROCESSING and _router_list[pid].is_stub:
				if DRAGON_DEBUG:
					print "Do not propagate UPDATE further as ASN %s is a stub." % (pid)
			else:
				_event_Scheduler.add(CEvent(self.getPeerLink(pid).next_delivery_time(self.id, update.size()), [self.id, pid, update], EVENT_RECEIVE))
		return change

	# Build update to send to peer pid for this prefix
	# Normal BGP only
	def sendtopeer(self, pid, prefix):
		update = CUpdate(prefix)
		node = self.loc_rib.search_exact(prefix)
		if node:
			if self.exportFilter(pid, prefix, node.data['best_path']):
				npath = self.exportAction(pid, prefix, node.data['best_path'])
				update.paths.append(npath)
		# compare update and rib_out
		return self.delivery(pid, prefix, update)

    #
    # Compute processing delay based on configured delay fonction
    #
	def processDelay(self):
		return toSystemTime(interpretDelayfunc(self, self.rand_seed, default_process_delay_func))

    #
    # Compute next processing time
    #
	def getIdelTime(self):
		if self.next_idle_time < _systime:
			self.next_idle_time = _systime
		self.next_idle_time = self.next_idle_time + self.processDelay()
		return self.next_idle_time

#
# Represents a BGP Update
#
class CUpdate:
	prefix = None # prefix
	paths = None # array of CPath
	fesn = None # forword edge sequence numbers

	def __init__(self, prefix):
		self.prefix = prefix
		self.paths = []

	def __str__(self):
		tmpstr = self.prefix + "("
		if len(self.paths) > 0:
			for p in self.paths:
				tmpstr = tmpstr + str(p)
		else:
			tmpstr = tmpstr + "W"
		tmpstr = tmpstr + ")"
		return tmpstr

	def size(self):
		sz = 4
		for p in self.paths:
			sz = sz + p.size()
		return sz

#
# Represents a BGP Path
#
class CPath:
	index = None # for single path routing, index=0; multipath routing, index=0,1,2,...
	src_pid = None

	#type = None
	weight = None
	local_pref = None
	med = None
	nexthop = None
	community = None
	alternative = None
	igp_cost = None
	aspath = None
	fesnpath = None

	def __init__(self):
		global default_local_preference, default_weight, ALTERNATIVE_NONE
		self.index = 0
		self.src_pid = None
		#self.type = ANNOUNCEMENT
		self.weight = default_weight
		self.local_pref = default_local_preference
		self.med = 0
		self.nexthop = ""
		self.igp_cost = 0
		self.community = []
		self.alternative = ALTERNATIVE_NONE
		self.aspath = ()

    #
    # Returns the size of the path in bytes
    #
	def size(self):
		return 4 + 4 + 4 + 4 + 4*len(self.community) + 2*len(self.aspath)
	
    #
    # Compare two paths for strict equivalence
    #
	def compareTo(self, path2):
		global bgp_always_compare_med
		if self.index != path2.index:
			return sgn(self.index - path2.index)
		#if self.type != path2.type:
		#	return sgn(self.type - path2.type)
		if (self.alternative == ALTERNATIVE_BACKUP or path2.alternative == ALTERNATIVE_BACKUP) and self.alternative != path2.alternative:
			return self.alternative - path2.alternative
		if self.weight != path2.weight:
			return sgn(path2.weight - self.weight)
		if self.local_pref != path2.local_pref:
			return sgn(path2.local_pref - self.local_pref)
		if len(self.aspath) != len(path2.aspath):
			return sgn(len(self.aspath) - len(path2.aspath))
		if len(self.aspath) > 0 and len(path2.aspath) > 0 and (((not bgp_always_compare_med) and self.aspath[0] == path2.aspath[0]) or bgp_always_compare_med) and self.med != path2.med:
			return sgn(self.med - path2.med)
		if self.igp_cost != path2.igp_cost:
			return self.igp_cost - path2.igp_cost
		if self.nexthop > path2.nexthop:
			return 1
		elif self.nexthop < path2.nexthop:
			return -1
		else:
			return 0

	def compareTo2(self, path2):
		result = self.compareTo(path2)
		if result != 0:
			return result
		return self.alternative - path2.alternative

    #
    # Build a new path with the same attributes
    #
	def copy(self, p2):
		self.index = p2.index
		self.src_pid = p2.src_pid
		#self.type = p2.type
		self.weight = p2.weight
		self.local_pref = p2.local_pref
		self.med = p2.med
		self.nexthop = p2.nexthop
		self.igp_cost = p2.igp_cost
		self.community = []
		self.community.extend(p2.community)
		self.aspath = p2.aspath[:]
		self.alternative = p2.alternative

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		tmpstr = str(self.index) + "/AS-PATH:" + str(self.aspath) + "/NH:" + str(self.nexthop)
		tmpstr += "/COMM:["
		if self.community:
			for comm in self.community:
				if comm == "1":
					tmpstr += "CUST"
				elif comm == "2":
					tmpstr += "PEER"
				elif comm == "3":
					tmpstr += "PROV"
		tmpstr += "]"
		return tmpstr
	
	def __eq__(self, other):
		return isinstance(other, self.__class__) and \
			self.local_pref == other.local_pref and self.nexthop == other.nexthop and \
			self.aspath == other.aspath
	
	def __hash__(self):
		return hash(self.local_pref) ^ hash(self.nexthop) ^ hash(self.aspath)
	
	#
	# Compare two CPaths object, i.e. check if purely BGP attributes are equals
	#
	def __cmp__(self, other):
		if self.weight != other.weight:
			return self.weight - other.weight
			
		if self.local_pref != other.local_pref:
			return self.local_pref - other.local_pref
			
		if self.med != other.med:
			return self.med - other.med
			
		if self.nexthop < other.nexthop:
			return -1
			
		if self.nexthop > other.nexthop:
			return 1
			
		if self.community < other.community:
			return -1
			
		if self.community > other.community:
			return 1
			
		if self.igp_cost != other.igp_cost:
			return self.igp_cost - other.igp_cost
			
		if len(self.aspath) < len(other.aspath):
			return -1
			
		if len(self.aspath) > len(other.aspath):
			return 1
		#if self.ibgp_ebgp != other.ibgp_ebgp : 
		#	return self.ibgp_ebgp - other.ibgp_ebgp
		return 0

#
# Represents a peer of a BGP router
#
class CPeer:
	id = None
	rib_in = None # key: prefix, store the paths received from peer
	rib_out = None # key: prefix, store the paths sent to peer
	out_queue = None # store the updates hold by MRAI timer
	rand_seed = None
	mrai_base = None
	route_reflector_client = None
	route_map_in = None
	route_map_out = None
	route_map_sorted = None
	fesnList = None
	sendFesnTable = None
	
	## DRAGON-specific
	peer_type = None

	def __str__(self):
		return str(self.id)

	def __init__(self, i, l):
		self.id = i
		self.link = l
		self.rib_in = {}
		self.rib_out = {}
		self.out_queue = []
		self.mrai_base = 0
		self.rand_seed = None
		self.route_map_in = None
		self.route_map_out = None
		self.route_map_sorted = False
		self.route_reflector_client = False

	def clear(self):
		del self.rib_in; self.rib_in = {}
		del self.rib_out; self.rib_out = {}
		del self.out_queue; self.out_queue = []

    #
    # Return computed value of the MRAI delay for this peer
    #
	def mrai_timer(self):
		global MRAI_JITTER, RANDOMIZED_KEY
		if MRAI_JITTER:
			if self.rand_seed is None:
				seed = str(self) + RANDOMIZED_KEY
				self.rand_seed = random.Random(seed)
			delay = self.mrai_base*(3.0 + self.rand_seed.random()*1.0)/4
		else:
			delay = self.mrai_base
		return toSystemTime(delay)

    #
    # Another computation of MRAI value
    #
	def random_mrai_wait(self):
		global RANDOMIZED_KEY
		if self.rand_seed is None:
			seed = str(self) + RANDOMIZED_KEY
			self.rand_seed = random.Random(seed)
		return toSystemTime(self.rand_seed.random()*self.mrai_base); 

    #
    # Add prefix to MRAI waiting sending queue.  Remove previous announcement because they are up to date
    #
	def enqueue(self, prefix):
		self.dequeue(prefix)
		self.out_queue.append(prefix)

    #
    # Remove prefix from MRAI waiting queue
    #
	def dequeue(self, prefix):
		if prefix in self.out_queue:
			self.out_queue.remove(prefix)

    #
    # return string representing path in adjribin for this prefix
    #
	def getRibInStr(self, prefix):
		tmpstr = "#" + self.id
		if self.rib_in.has_key(prefix):
			for p in self.rib_in[prefix]:
				tmpstr = tmpstr + "(" + str(p) + ")"
		return tmpstr
	
    #
    # Sort route maps for this peer
    #
	def sortRouteMap(self):
		if self.route_map_out is not None:
			self.route_map_out.sort(cmpRouteMap)
		if self.route_map_in is not None:
			self.route_map_in.sort(cmpRouteMap)
		self.route_map_sorted = True

    #
    # Return outfilters
    #
	def getRouteMapOut(self):
		if self.route_map_out is not None:
			if not self.route_map_sorted:
				self.sortRouteMap()
			return self.route_map_out
		else:
			return []
	
    #
    # Return infilters
    #
	def getRouteMapIn(self):
		if self.route_map_in is not None:
			if not self.route_map_sorted:
				self.sortRouteMap()
			return self.route_map_in
		else:
			return []

#
# Represents a BGP session
#
class CLink:
	start = None # CRouter
	end = None # CRouter
	status = None # LINK_UP/LINK_DOWN
	cost = None
	bandwidth = None
	#delayfunc = None
	rand_seed = None
	next_delivery_time_start = None
	next_delivery_time_end = None

	def __str__(self):
		return str(self.start) + "-" + str(self.end)

	def __init__(self, s, e):
		global default_link_delay_func, LINK_UP
		self.start = s
		self.end = e
		self.status = LINK_UP
		self.cost = 0
		self.bandwidth = 100000000 # 100MB as default
		#self.delayfunc = ["deterministic", 0.1]
		#self.delayfunc = default_link_delay_func #["uniform", 0.01, 0.1]
		self.rand_seed = None
		self.next_deliver_time_start = 0
		self.next_deliver_time_end = 0

    #
    # Return time of arrival at the other end of the link
    #
	def next_delivery_time(self, me, size):
		if me == self.start:
			if self.next_delivery_time_start < _systime:
				self.next_delivery_time_start = _systime
			self.next_delivery_time_start = self.next_delivery_time_start + self.link_delay(size)
			return self.next_delivery_time_start
		elif me == self.end:
			if self.next_delivery_time_end < _systime:
				self.next_delivery_time_end = _systime
			self.next_delivery_time_end = self.next_delivery_time_end + self.link_delay(size)
			return self.next_delivery_time_end

	def interpretDelayfunc(self):
		global _link_delay_table
		if _link_delay_table.has_key(self):
			return interpretDelayfunc(self, self.rand_seed, _link_delay_table[self])
		else:
			return interpretDelayfunc(self, self.rand_seed, default_link_delay_func)

	def link_delay(self, size): # queuing delay + propagation delay
		return toSystemTime(self.interpretDelayfunc() + size*1.0/self.bandwidth)

    #
    # Return other end of the link
    #
	def getPeer(self, me):
		if self.start == me:
			return end
		elif self.end == me:
			return start
		else:
			print "Error, wrong link"
			sys.exit(-1)

    #
    # Return BGP type of the link
    #
	def ibgp_ebgp(self):
		global _router_list
		if _router_list[self.start].asn == _router_list[self.end].asn:
			return IBGP_SESSION
		else:
			return EBGP_SESSION

#
# Represents a BGP route map, i.e.  BGP filter
#
class CRouteMap:
	name = None
	priority = None
	permit = None
	match = None
	action = None

	def __init__(self, n, pmt, pr):
		self.name = n
		if pmt == "permit":
			self.permit = True
		else:
			self.permit = False
		self.priority = pr
		self.match = []
		self.action = []

    #
    # Check if this path match the route map conditions
    #
	def isMatch(self, prefix, path):
		i = 0
		while i < len(self.match):
			cond = self.match[i]
			if cond[0] == "community-list":
				if len(cond) >= 3 and cond[2] == "exact":
					cmlist = cond[1].split(":")
					cmlist.sort()
					if cmlist != path.community:
						return False
				elif len(cond) >= 3 and cond[2] == "any":
					cmlist = cond[1].split(":")
					for comm in cmlist:
						if comm in path.community:
							return True
					return False
				elif cond[1] not in path.community:
					return False
			elif cond[0] == "as-path":
				pathstr = array2str(path.aspath, "_")
				if not re.compile(cond[1]).match(pathstr):
					return False
			elif cond[0] == "ip" and cnd[1] == "address":
				if cond[2] != prefix:
					return False
			elif cond[0] == "metric":
				if int(cond[1]) != path.med:
					return False
			i = i + 1
		return True

    #
    # Perform action of the route map on the path
    #
	def performAction(self, path):
		i = 0
		while i < len(self.action):
			act = self.action[i]
			if act[0] == "local-preference":
				path.local_pref = int(act[1])
			elif act[0] == "community":
				if act[1] == "none":
					path.community = []
				else:
					if len(act) >= 3 and act[2] == "additive":
						path.community.extend(act[1].split(":"))
					else:
						path.community = act[1].split(":")
					path.community.sort()
			elif act[0] == "as-path" and act[1] == "prepend":
				j = 0
				while j < len(act) - 2:
					path.aspath.insert(j, int(act[2+j]))
					j = j + 1
			elif act[0] == "metric":
				path.med = int(act[1])
			i = i + 1
		return path

#
# Represents a BGP event
#
class CEvent:
	seq = 0 # sequence
	time = None # when
	param = None # where
	type = None # what

	def __init__(self, tm, pr, t):
		self.seq = getSequence()
		self.time = tm
		self.param = pr
		self.type = t

    #
    # Print event representation on stdout
    #
	def showEvent(self):
		global SHOW_RECEIVE_EVENTS, _router_list, SHOW_DEBUG
		if self.type == EVENT_RECEIVE:
			[rtid, rvid, update] = self.param
			if SHOW_RECEIVE_EVENTS:
				print formatTime(self.time), str(_router_list[rvid]), "receive", str(_router_list[rtid]), update
		elif self.type == EVENT_UPDATE:
			[rtid, prefix] = self.param
			#print self.time, rtid, "update", prefix
		elif self.type == EVENT_MRAI_EXPIRE_SENDTO:
			[sdid, rvid, prefix] = self.param
			if SHOW_DEBUG:
				print formatTime(self.time), sdid, "mrai expires", rvid, prefix
		elif self.type == EVENT_LINK_DOWN:
			[rt1, rt2] = self.param
			if SHOW_LINK_EVENTS:
				print formatTime(self.time), "link", str(_router_list[rt1]), "-", str(_router_list[rt2]), "down"
		elif self.type == EVENT_LINK_UP:
			[rt1, rt2] = self.param
			if SHOW_LINK_EVENTS:
				print formatTime(self.time), "link", str(_router_list[rt1]), "-", str(_router_list[rt2]), "up"
		elif self.type == EVENT_ANNOUNCE_PREFIX:
			[rtid, prefix] = self.param
		elif self.type == EVENT_WITHDRAW_PREFIX:
			[rtid, prefix] = self.param
			print formatTime(self.time), "router", str(_router_list[rtid]), "withdraws", prefix
		elif self.type == EVENT_TERMINATE:
			print formatTime(self.time), "simulation terminates"
		elif self.type == EVENT_SHOW_ALL_RIBS:
			print formatTime(self.time), "printing the content of all the RIBS ..."
		elif self.type == EVENT_RESET_COUNTERS:
			if SHOW_DEBUG:
				print formatTime(self.time), "resetting all the counters ..."
		elif self.type == EVENT_ACTIVATE_DEAGGREGATES:
			if SHOW_DEBUG:
				print formatTime(self.time), "activating de-aggregates announcements ..."
		elif self.type == EVENT_OUTPUT_UPDATES:
			print formatTime(self.time), "output numbers of updates to file ..."
		elif self.type == EVENT_ACTIVATE_DEBUG:
			print formatTime(self.time), "activating DEBUG mode ..."
		elif self.type == EVENT_START_TRACK_TIME:
			print formatTime(self.time), "resetting counter for accounting for simulation time ..."
		elif self.type == EVENT_STOP_TRACK_TIME:
			print formatTime(self.time), "outputting simulation time since last event ..."
		else:
			if SHOW_DEBUG:
				print formatTime(self.time), "unknown event ..."

    #
    # Perform corresponding action when the event happens
    #
	def process(self):
		global _router_list, DISABLE_DEAGGREGATES_ANNOUNCEMENT, start_time, cur_time
		
		global DRAGON_DEBUG
		global SHOW_SEND_EVENTS
		global SHOW_DEBUG
		global SHOW_LINK_EVENTS
		global SHOW_ANNOUNCE_EVENTS
		
		self.showEvent()
		if self.type == EVENT_RECEIVE:
			[rtid, rvid, update] = self.param
			_router_list[rvid].receive(rtid, update)
		elif self.type == EVENT_UPDATE:
			[rtid, prefix] = self.param
			_router_list[rtid].update(prefix)
		elif self.type == EVENT_MRAI_EXPIRE_SENDTO:
			[sdid, rvid, prefix] = self.param
			_router_list[sdid].resetMRAI(rvid, prefix)
			_router_list[sdid].sendto(rvid, prefix)
		elif self.type == EVENT_LINK_DOWN:
			[rt1, rt2] = self.param
			lk = getRouterLink(rt1, rt2)
			lk.status = LINK_DOWN
			_router_list[rt1].peerDown(rt2)
			_router_list[rt2].peerDown(rt1)
		elif self.type == EVENT_LINK_UP:
			[rt1, rt2] = self.param
			lk = getRouterLink(rt1, rt2)
			lk.status = LINK_UP
			_router_list[rt1].peerUp(rt2)
			_router_list[rt2].peerUp(rt1)
		elif self.type == EVENT_ANNOUNCE_PREFIX:
			[rtid, prefix] = self.param
			if DRAGON_ACTIVATED:
				_router_list[rtid].compute_local_announcements(prefix)
			else:
				_router_list[rtid].announce_prefix(prefix)
		elif self.type == EVENT_WITHDRAW_PREFIX:
			[rtid, prefix] = self.param
			_router_list[rtid].withdraw_prefix(prefix)
		elif self.type == EVENT_TERMINATE:
			return -1
		elif self.type == EVENT_SHOW_ALL_RIBS:
			print "-----======$$$$$$$$ ALL_RIBS $$$$$$$$$=======------"
			for rt in sorted(_router_list.values(), key=lambda router: router.asn):
				rt.showAllRib()
		elif self.type == EVENT_RESET_COUNTERS:
			for rt in _router_list.values():
				for neighbor in rt.num_updates:
					rt.num_updates[neighbor] = 0
		elif self.type == EVENT_ACTIVATE_DEAGGREGATES:
			DISABLE_DEAGGREGATES_ANNOUNCEMENT = False
		elif self.type == EVENT_OUTPUT_UPDATES:
			[filename] = self.param
			output_number_updates(filename)
		elif self.type == EVENT_ACTIVATE_DEBUG:
			DRAGON_DEBUG = True
			SHOW_SEND_EVENTS = True
			SHOW_DEBUG = True
			SHOW_LINK_EVENTS = True
			SHOW_ANNOUNCE_EVENTS = True
		elif self.type == EVENT_START_TRACK_TIME:
			start_time = float(formatTime(self.time))
			cur_time = start_time
		elif self.type == EVENT_STOP_TRACK_TIME:
			[filename, in_cone] = self.param
			output_processing_time(filename, in_cone)
		return 0

    #
    # Compare two event, based on happening time
    #
	def __cmp__(self, o):
		if self.time != o.time:
			return self.time - o.time
		return self.seq - o.seq

#
# Represents an ordered list
#
class COrderedList:
	data = [];
	#
	# Constructor
	#
	def __init__(self):
		self.data = [];

	#
	# Insert object o in the correct position in the ordered list, dichotomical search. Do nothing is object is present
	# 
	def add(self, o):
		
		## DRAGON
		if DRAGON_ACTIVATED:
			if o.type == EVENT_ANNOUNCE_PREFIX:
				originator = o.param[0]
				pfx = o.param[1]
				allocated_prefixes.add(pfx)
				router2prefix_mapping[originator].append(pfx)
		
		start = 0;
		end = len(self.data)-1;
		while start <= end:
			j = (start + end)/2;
			if "__cmp__" in dir(o):
				result = o.__cmp__(self.data[j]);
				if result == 0:
					return;
				elif result > 0:
					start = j + 1;
				else:
					end = j - 1;
			else:
				if o == self.data[j]:
					return;
				elif o > self.data[j]:
					start = j + 1;
				else:
					end = j - 1;
		self.data.insert(start, o);

	#
	# Return item at index idx
	#
	def __getitem__(self, idx):
		return self.data[idx];
    
	#
	# Return len of the list
	#
	def __len__(self):
		return len(self.data);

	#
	# Remove and returns element at index idx
	#
	def pop(self, idx):
		return self.data.pop(idx);

def getRouterLink(id1, id2):
	global _router_graph
	if id1 > id2:
		rt1 = id1
		rt2 = id2
	else:
		rt2 = id1
		rt1 = id2
	if not _router_graph.has_key(rt1):
		_router_graph[rt1] = {}
	if not _router_graph[rt1].has_key(rt2):
		lk = CLink(rt1, rt2)
		_router_graph[rt1][rt2] = lk
	return _router_graph[rt1][rt2]

def array2str(path, sep):
	if len(path) == 0:
		return ""
	else:
		tmpstr = str(path[0])
		for i in range(1, len(path)):
			tmpstr = tmpstr + sep + str(path[i])
		return tmpstr

def cmpRouteMap(rm1, rm2):
	global _route_map_list
	return _route_map_list[rm1].priority - _route_map_list[rm2].priority

###################LOOP DETECTION###loop detection###Loop Detection################

LOOPCHECK_LOOP    = -2
LOOPCHECK_FAILURE = -1
LOOPCHECK_SUCESS  = 0

def looptype(t):
	global LOOPCHECK_FAILURE, LOOPCHECK_SUCESS, LOOPCHECK_LOOP
	if t == LOOPCHECK_FAILURE:
		return "FAIL"
	elif t == LOOPCHECK_LOOP:
		return "LOOP"
	elif t >= LOOPCHECK_SUCESS:
		return "SUCC"
	else:
		return "UNKN"

_infect_nodes = {}

def forwardingCheck(rt, prefix):
	global LOOPCHECK_FAILURE, LOOPCHECK_SUCESS, LOOPCHECK_LOOP, _loop_list
	path = [rt.id]
	result = LOOPCHECK_FAILURE # blackhole
	while rt.loc_rib.has_key(prefix) and len(rt.loc_rib[prefix]) > 0:
		if rt.loc_rib[prefix][0].src_pid == None:
			result = LOOPCHECK_SUCESS # sucess
			break
		rt = _router_list[rt.loc_rib[prefix][0].src_pid]
		path.append(rt.id)
		if rt.id in path[:-1]:
			del path[-1]
			result = LOOPCHECK_LOOP
			break
	#print getSystemTimeStr() + " " + looptype(result) + " " + array2str(path, "-")
	distance = {}
	if result == LOOPCHECK_SUCESS:
		i = 0
		while i < len(path):
			distance[path[i]] = len(path) - i
			i = i + 1
	else:
		for rt in path:
			distance[rt] = result
	queue = path
	while len(queue) > 0:
		rid = queue.pop(0)
		for pid in _router_list[rid].peers.keys():
			if not distance.has_key(pid):
				peer = _router_list[pid]
				if peer.loc_rib.has_key(prefix) and len(peer.loc_rib[prefix]) > 0 and peer.loc_rib[prefix][0].src_pid is not None and peer.loc_rib[prefix][0].src_pid == rid:
					queue.append(pid)
					if result >= LOOPCHECK_SUCESS:
						distance[pid] = distance[rid] + 1
					else:
						distance[pid] = result
	for node in distance.keys():
		addInfectNode(node, distance[node])

def addInfectNode(node, result):
	global _infect_nodes
	if not _infect_nodes.has_key(node):
		_infect_nodes[node] = [_systime, result]
	else:
		if _infect_nodes[node][1] != result:
			removeInfectNode(node, result)
			_infect_nodes[node] = [_systime, result]

def removeInfectNode(node, result):
	global _infect_nodes, _router_list
	if _infect_nodes.has_key(node):
		print "FCK:", formatTime(_systime), looptype(result), result, "<<", formatTime(_infect_nodes[node][0]), looptype(_infect_nodes[node][1]), _infect_nodes[node][1], formatTime(_systime - _infect_nodes[node][0]), _router_list[node]
		del _infect_nodes[node]

###################################################################################
def splitstr(line, pat):
	ele = []
	i = 0
	tmpstr = ""
	while i <= len(line):
		if i < len(line) and line[i] != pat:
			tmpstr = tmpstr + line[i]
		else:
			if tmpstr != "":
				ele.append(tmpstr.lower())
				tmpstr = ""
		i = i + 1
	return ele

def readnextcmd(fh):
	try:
		line = fh.readline()
		while len(line) > 0 and (line[0] == '!' or len(splitstr(line[:-1], ' ')) == 0):
			line = fh.readline()
		return splitstr(line[:-1], ' ')
	except:
		print "Exception: ", sys.exc_info()[0]
		raise

def interpretBandwidth(line):
	if line[-1] == 'M' or line[-1] == 'm':
		return float(line[:-1])*1000000
	elif line[-1] == 'K' or line[-1] == 'k':
		return float(line[:-1])*1000
	elif line[-1] == 'G' or line[-1] == 'g':
		return float(line[:-1])*1000000000
	else:
		return float(line)

def interpretDelay(param):
	if param[0] not in ["deterministic", "normal", "uniform", "exponential", "pareto", "weibull"]:
		print "Distribution", param[0], "in", param, "is not supported!"
		sys.exit(-1)
	tmparray = [param[0]]
	for i in range(1, len(param)):
		tmparray.append(float(param[i]))
	return tmparray

def activate_debug():
	global SHOW_SEND_EVENTS
	global SHOW_FINAL_RIBS
	global SHOW_DEBUG
	global SHOW_LINK_EVENTS
	global SHOW_ANNOUNCE_EVENTS
	global DRAGON_DEBUG
	
	SHOW_SEND_EVENTS = True
	SHOW_FINAL_RIBS = True
	SHOW_DEBUG = True
	SHOW_LINK_EVENTS = True
	SHOW_ANNOUNCE_EVENTS = True
	DRAGON_DEBUG = True

def readConfig(lines):
	global SHOW_UPDATE_RIBS, SHOW_RECEIVE_EVENTS, SHOW_FINAL_RIBS, wrate, always_mrai, ssld,\
		bgp_always_compare_med, MRAI_JITTER, MAX_PATH_NUMBER, CHECK_LOOP, SHOW_DEBUG, RANDOMIZED_KEY,\
		SHOW_SEND_EVENTS, default_link_delay_func, default_process_delay_func, _link_delay_table

	curRT = None
	curNB = None
	curMap = None
	curAS = None
	
	for line in lines:
		line = line.strip()
		
		if line == "" or line[0] == "!":
			continue
			
		cmd = line.split()
		
		if cmd[0] == "router" and cmd[1] == "bgp":
			curAS = int(cmd[2])
		elif cmd[0] == "bgp" and cmd[1] == "router-id":
			id = cmd[2]
			curRT = CRouter(curAS, id)
			_router_list[id] = curRT
		elif cmd[0] == "bgp":
			if cmd[1] == "cluster-id":
				curRT.route_reflector = True
				# print "router", str(curRT), curRT.route_reflector
			elif cmd[1] == "prefix-based-timer":
				curRT.mrai_setting = MRAI_PREFIX_BASED
			else:
				print "unknown bgp configuration", cmd[1], "in", cmd
				sys.exit(-1)
		elif cmd[0] == "neighbor":
			peerid = cmd[1]
			if not curRT.peers.has_key(peerid):
				link = getRouterLink(curRT.id, peerid)
				curNB = CPeer(peerid, link)
				curRT.peers[peerid] = curNB
			if cmd[2] == "route-reflector-client":
				curNB.route_reflector_client = True
			elif cmd[2] == "route-map":
				if cmd[4] == "in":
					if curNB.route_map_in is None:
						curNB.route_map_in = []
					curNB.route_map_in.append(cmd[3])
				elif cmd[4] == "out":
					if curNB.route_map_out is None:
						curNB.route_map_out = []
					curNB.route_map_out.append(cmd[3])
			elif cmd[2] == "advertisement-interval": # in seconds
				curNB.mrai_base = float(cmd[3])
			elif cmd[2] == "remote-as":
				x = 1 # do nothing
				if len(cmd) > 4:
					if cmd[4] == "cust":
						curRT.peers[peerid].peer_type = CUSTOMER
						bgp_topology.add_edge(curRT.id, peerid, type=1)
					elif cmd[4] == "peer":
						curRT.peers[peerid].peer_type = PEER
						bgp_topology.add_edge(curRT.id, peerid, type=2)
					elif cmd[4] == "prov":
						curRT.peers[peerid].peer_type = PROVIDER
						bgp_topology.add_edge(curRT.id, peerid, type=3)
					else:
						print "unknown remote-as configuration", cmd[4], "in", cmd
						sys.exit(-1)
			else:
				print "unknown neighbor configuration", cmd[2], "in", cmd
				sys.exit(-1)
		# route-map <name> permit/deny priority
		elif cmd[0] == "route-map":
			if len(cmd) >= 4:
				pr = int(cmd[3])
			else:
				pr = 10
			curMap = CRouteMap(cmd[1], cmd[2], pr)
			_route_map_list[cmd[1]] = curMap
		elif cmd[0] == "set":
			curMap.action.append(cmd[1:])
		elif cmd[0] == "match":
			curMap.match.append(cmd[1:])
		elif cmd[0] == "link":
			lk = getRouterLink(cmd[1], cmd[2])
			if cmd[3] == "cost":
				lk.cost = int(cmd[4])
			elif cmd[3] == "bandwidth":
				lk.bandwidth = interpretBandwidth(cmd[4])
			elif cmd[3] == "delay":
				_link_delay_table[lk] = interpretDelay(cmd[4:])
			else:
				print "unknown link configuration", cmd[3], "in", cmd
				sys.exit(-1)
		elif cmd[0] == "event":
			if cmd[1] == "announce-prefix": # event announce-prefix x.x.x.x x.x.x.x sec
				_event_Scheduler.add(CEvent(toSystemTime(float(cmd[4])), [cmd[2], cmd[3]], EVENT_ANNOUNCE_PREFIX))
			elif cmd[1] == "withdraw-prefix": # event withdraw-prefix x.x.x.x x.x.x.x sec
				_event_Scheduler.add(CEvent(toSystemTime(float(cmd[4])), [cmd[2], cmd[3]], EVENT_WITHDRAW_PREFIX))
			elif cmd[1] == "link-down": # event link-down x.x.x.x x.x.x.x sec
				_event_Scheduler.add(CEvent(toSystemTime(float(cmd[4])), [cmd[2], cmd[3]], EVENT_LINK_DOWN))
			elif cmd[1] == "link-up": # event link-up x.x.x.x x.x.x.x sec
				_event_Scheduler.add(CEvent(toSystemTime(float(cmd[4])), [cmd[2], cmd[3]], EVENT_LINK_UP))
			elif cmd[1] == "terminate":
				_event_Scheduler.add(CEvent(toSystemTime(float(cmd[2])), [], EVENT_TERMINATE))
			else:
				print "unknown event", cmd[1], "in", cmd
				sys.exit(-1)
		elif cmd[0] == "debug":
			if cmd[1] == "show-update-ribs":
				SHOW_UPDATE_RIBS = True
			elif cmd[1] == "show-receive-events":
				SHOW_RECEIVE_EVENTS = True
			elif cmd[1] == "show-final-ribs":
				SHOW_FINAL_RIBS = True
			elif cmd[1] == "show-debug":
				SHOW_DEBUG = True
			elif cmd[1] == "check-loop":
				CHECK_LOOP = True
			elif cmd[1] == "show-send-events":
				SHOW_SEND_EVENTS = True
			else:
				print "unknown debug option", cmd[1], "in", cmd
				sys.exit(-1)
		elif cmd[0] == "config":
			if cmd[1] == "mrai-jitter":
				if cmd[2] == "true":
					MRAI_JITTER = True
				else:
					MRAI_JITTER = False
			elif cmd[1] == "always-compare-med":
				bgp_always_compare_med = True
			elif cmd[1] == "withdraw-rate-limiting":
				wrate = True
			elif cmd[1] == "sender-side-loop-detection":
				ssld = True
			elif cmd[1] == "always-mrai":
				always_mrai = True
			elif cmd[1] == "randomize-key":
				if cmd[2] == "random":
					RANDOMIZED_KEY = str(time.time())
				else:
					RANDOMIZED_KEY = cmd[2]
			elif cmd[1] == "default-link-delay":
				default_link_delay_func = interpretDelay(cmd[2:])
			elif cmd[1] == "default-process-delay":
				default_process_delay_func = interpretDelay(cmd[2:])
			else:
				print "unknown config option", cmd[1], "in", cmd
				sys.exit(-1)
		else:
			print "unkown command", cmd[0], "in", cmd
			sys.exit(-1)

#
# Initialization of global variables
#
def init(output='sim_output'):
	global _event_Scheduler
	global _systime
	global _router_list
	global _router_graph #Graph of BGP sessions
	global _route_map_list
	
	global allocated_prefixes
	global router2prefix_mapping
	global pfx2children_mapping
	global bgp_topology
	global output_file
	
	_event_Scheduler = COrderedList()
	_systime = 0	
	_router_list = {}
	_router_graph = {}
	_route_map_list = {}
	
	allocated_prefixes = radix.Radix()
	router2prefix_mapping = defaultdict(list)
	pfx2children_mapping = {}
	bgp_topology = nx.DiGraph()
	output_file = output

def populate_type():
	for router_id in _router_list:
		is_stub = True	
		for peer_id in _router_list[router_id].peers:
			if _router_list[router_id].peers[peer_id].peer_type == CUSTOMER:
				is_stub = False
		_router_list[router_id].is_stub = is_stub

def loadConfig(config):
	readConfig(config.splitlines())
#
# Parse config from filename and build topology
#
def readConfigFile(filename):
	try:
		f = open(filename, "r")
		readConfig(f)
		f.close()
	except IOError :
		print "Could not open file : ", filename
		sys.exit(-1)

def output_number_updates(filename):
	if DRAGON_ACTIVATED:
		filename += '.dragon.update.bz2'
	else:
		filename += '.bgp.update.bz2'
	
	output_updates = bz2.BZ2File(filename, 'w')
	for rt in sorted(_router_list.values(), key=lambda router: router.asn):
		for neighbor in rt.num_updates:
			output_updates.write("%s %s %d\n" % (rt.id, neighbor, rt.num_updates[neighbor]))
	output_updates.close()


def output_processing_time(filename, in_cone):
	global cur_time, start_time
	
	if DRAGON_ACTIVATED:
		filename += '.dragon.time'
	else:
		filename += '.bgp.time'
	
	output_file = open(filename, 'a')
	output_file.write("%d %.2f\n" % (in_cone, cur_time - start_time))
	output_file.close()


def run(pfx_to_mult=None):
	global _systime, _event_Scheduler, allocated_prefixes, pfx2children_mapping, parentless_prefixes, pfx_to_multiplicator_map, cur_time
	
	pfx_to_multiplicator_map = pfx_to_mult
	
	if DRAGON_ACTIVATED:
		pfx2children_mapping = build_pfx2children_mapping(allocated_prefixes.prefixes())
		parentless_prefixes = return_parentless_prefixes(allocated_prefixes.prefixes())
	
	while len(_event_Scheduler) > 0:
		cur_event = _event_Scheduler.pop(0)
		_systime = cur_event.time
		if (cur_event.type != EVENT_START_TRACK_TIME) and (cur_event.type != EVENT_STOP_TRACK_TIME):
			cur_time = float(formatTime(_systime))
		if cur_event.process() == -1:
			break
	
	if CHECK_LOOP:
		nodes = _infect_nodes.keys()
		for node in nodes:
			removeInfectNode(node, LOOPCHECK_FAILURE)
	
	if SHOW_FINAL_RIBS:
		print "-----======$$$$$$$$ FINISH $$$$$$$$$=======------"
		for rt in sorted(_router_list.values(), key=lambda router: router.asn):
			rt.showAllRib()
	
	if SHOW_STATISTICS:
		output_number_updates(output_file)

#
# Launch simulation from string config
#
def runConfig(config):
	init()
	loadConfig(config)
	run()

#
# Launch simulation from file
# 
def runConfigFile(filename):
	init()
	readConfigFile(filename)
	run()

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print "Usage: %s [config_file]" % (sys.argv[0])
		sys.exit(-1)
	runConfigFile(sys.argv[1])
