import sys
import networkx as nx
import random

from collections import defaultdict
from ipaddr import IPv4Network, collapse_address_list

def compute_delta_between_prefix_list(prefixes_before, prefixes_after):
    
    delta_prefixes = []
    
    new_advertised = set(prefixes_after) - set(prefixes_before)
    new_withdraw = set(prefixes_before) - set(prefixes_after)
    
    for pfx in new_advertised:
        delta_prefixes.append((pfx, True))
    
    for pfx in new_withdraw:
        delta_prefixes.append((pfx, False))
    
    return delta_prefixes

def compute_aggregate(parent_str, reachable_children_and_types):
	
	announce_to_children = []
	announce_to_peer_prov = []
	all_children_prefixes = []
	
	for (pfx, type_) in reachable_children_and_types:
		
		all_children_prefixes.append(pfx)
		
		if (type_ == 0 or type_ == 1):
			announce_to_children.append(pfx)
			announce_to_peer_prov.append(pfx)
		elif (type_ != 4):
			announce_to_children.append(pfx)
	
	#a = compute_aggregate_helper(parent_str, list(set(all_children_prefixes) - set(announce_to_children)))
	#b = compute_aggregate_helper(parent_str, list(set(all_children_prefixes) - set(announce_to_peer_prov)))
	
	
	return compute_aggregate_helper(parent_str, list(set(all_children_prefixes) - set(announce_to_peer_prov)))

def compute_aggregate_helper(parent_str, unreachable_children_lst_str):
	
	if not unreachable_children_lst_str:
		return [parent_str]
	
	parent_pfx = IPv4Network(parent_str)
	child_pfxes = [IPv4Network(child_str) for child_str in unreachable_children_lst_str]
	
	len_diff = max([child_pfx.prefixlen for child_pfx in child_pfxes]) - parent_pfx.prefixlen
	
	assert(len_diff > 0)
	
	subnets = set(parent_pfx.subnet(prefixlen_diff=len_diff)) - set(child_pfxes)
	
	return [str(pfx) for pfx in collapse_address_list(subnets)]

def return_parentless_prefixes(allocated_prefixes):
	parentless_prefixes = set()
	allocated_prefixes = sorted([IPv4Network(pfx) for pfx in allocated_prefixes])
	
	for allocated_pfx in allocated_prefixes:
		is_parentless = True
		for pfx in allocated_prefixes:
			if pfx != allocated_pfx and allocated_pfx in pfx:
				is_parentless = False
		if is_parentless:
			parentless_prefixes.add(str(allocated_pfx))
	
	return parentless_prefixes

def build_pfx2children_mapping(allocated_prefixes):
	pfx2children = {}
	
	# Sort the allocated prefixes 
	# from short to long prefixes
	allocated_prefixes = sorted([IPv4Network(pfx) for pfx in allocated_prefixes])
	
	for allocated_pfx in allocated_prefixes:
		for pfx in pfx2children:
			if allocated_pfx in pfx:
				pfx2children[pfx].append(allocated_pfx)
		pfx2children[IPv4Network(allocated_pfx)] = []
	
	return pfx2children

def assign_prefixes_to_topology(input_graph, prefixes):
	assignments = []

	## all stubs are candidate
	candidate_stubs = []
	prefixes.sort(reverse=True)

	for node in input_graph:
		if not [neigh for (neigh, data) in input_graph[node].items() if data['type'] == 1]:
			candidate_stubs.append(node)
	
	random.shuffle(candidate_stubs)
	
	selected_path = None

	while candidate_stubs:
		candidate = candidate_stubs.pop(0)
		paths = [p for p in recursive_dfs(input_graph, candidate) if len(p) >= len(prefixes)]
		if paths:
			selected_path = random.choice(paths)
			break
			
	if selected_path is None:
		print "Error. I was not able to assign prefixes: %s to the topology. Too many of them?" % (prefixes)
		sys.exit(-1)
	else:
		for i in range(len(prefixes)):
			assignments.append((selected_path[i], prefixes[i]))
	
	return assignments

#def return_cone(input_graph, node, destination_nodes=[]):
#	recursive_dfs_links(input_graph, node, destination_nodes=destination_nodes, edge_type=1)
#	return [(a,b) for (a,b,data) in input_graph.edges(data=True) if 'cone' in data]

def recursive_cone_dfs(input_graph, node, cone, visited, destination_nodes, edge_type=3):
	neighbors = [neigh for (neigh, data) in input_graph[node].items() if data['type'] == edge_type and (node, neigh) not in visited]
	if not neighbors:
		if node not in destination_nodes:
			return False
		else:
			return True
	else:
		found_path = False
		for neighbor in neighbors:
			visited.add((node,neighbor))
			if recursive_cone_dfs(input_graph, neighbor, cone, visited, destination_nodes, edge_type):
				cone.add((node, neighbor))
				found_path = True
		return (found_path or node in destination_nodes)

def return_deaggregation_triggering_link(cone_links, parent_node, destination_nodes):
	g = nx.DiGraph()

	deaggregation_triggering_links = set()
	
	for (head, tail) in cone_links:
		g.add_edge(head, tail)
	
	for (head,tail) in cone_links:
		g.remove_edge(head, tail)
		paths = nx.single_source_shortest_path(g, parent_node)
		for dest in destination_nodes:
			if dest not in paths:
				deaggregation_triggering_links.add((head,tail))
		g.add_edge(head,tail)
	
	return deaggregation_triggering_links

def recursive_dfs(input_graph, node, destination_nodes=[], edge_type=3):
	neighbors = [neigh for (neigh, data) in input_graph[node].items() if data['type'] == edge_type]
		
	if not neighbors:
		if node not in destination_nodes:
			return [None]
		else:
			return [[node]]
	else:
		paths = []		
		if node in destination_nodes:
			paths.append([node])
		for neighbor in neighbors:
			for sub_path in recursive_dfs(input_graph, neighbor, destination_nodes, edge_type):
				if sub_path is not None:
					paths.append([node] + sub_path)
		#print "Paths from node %s: %s" % (node, paths)
		return paths

def get_prefix_subtree(nb_prefixes = 3, initial_subnet_size = 16, incr = 2):
	prefixes = []
	ip_block = IPv4Network('10.0.0.0/' + str(initial_subnet_size))
	cur_prefix_len = initial_subnet_size

	# first, we generate nb_prefixes
	while len(prefixes) != nb_prefixes:
		pfx = random.choice(ip_block.subnet(prefixlen_diff=incr))
		prefixes.append(pfx)
		cur_prefix_len += incr
		ip_block = IPv4Network(str(pfx.network) + '/' + str(cur_prefix_len))
	
	return prefixes

def compute_levels(input_graph):
	# Tiers are defined as the shortest distance
	# from a Tier 1
	tiers = defaultdict(set)

	## stubs
	cur_tier = 0
	for node in input_graph:
		if not [x for x in input_graph[node].values() if x['type'] == 1]:
			tiers[cur_tier].add(node)
			
	cur_tier = 1
	while set(input_graph.nodes()) - set.union(*tiers.values()):
		#print "cur_tier: %d, nb_left: %s" % (cur_tier, len(set(input_graph.nodes()) - set.union(*tiers.values())))
		for node in set(input_graph.nodes()) - set.union(*tiers.values()):
			#print "node: %s, children: %s, previous_tier: %s" % (node, set([neigh for (neigh, data) in input_graph[node].items() if data['type'] == 1]),\
				 #set.union(*[value for t,value in tiers.items() if t < cur_tier]))
			if set([neigh for (neigh, data) in input_graph[node].items() if data['type'] == 1]).issubset(\
				set.union(*[value for t,value in tiers.items() if t < cur_tier])):
				tiers[cur_tier].add(node)
		cur_tier += 1
	return tiers

def get_topology_from_gitle_graph(input_file):
	g = nx.DiGraph()
	f = open(input_file, 'r')
	for line in f:
		splitted = line.split()
		if len(splitted) != 3:
			pass
		else:
			head = int(splitted[0])
			tail = int(splitted[1])
			type_ = int(splitted[2])
			if type_ == 0:
				# only add one direction since the other
				# direction will be at another line
				g.add_edge(head, tail, type=2)
			elif type_ == 1:
				# add the two directions in one go
				g.add_edge(tail, head, type=1)
				g.add_edge(head, tail, type=3)
			else:
				print "Error: Unknown type encountered when reading line %s" % (line)
	f.close()
	return g

def topology_to_graph(input_file):	
	g = nx.DiGraph()
	f = open(input_file, 'r')
	for line in f:
		splitted = line.split()
		head = int(splitted[0])
		tail = int(splitted[1])
		type_ = int(splitted[2])
		g.add_edge(head, tail, type=type_)
	f.close()
	return g

def get_stubs(input_file):
	stubs = []
	f = open(input_file, 'r')
	for line in f:
		splitted = line.split()
		stubs.append(int(splitted[0]))
	f.close()
	return stubs

def get_prefix_to_originator(input_file):
	prefix2originator = {}
	f = open(input_file, 'r')
	for line in f:
		splitted_line = line.split()
		prefix = splitted_line[0]
		originator = int(splitted_line[1])
		prefix2originator[prefix] = originator
	f.close()
	return prefix2originator

def get_list_of_originated_prefixes(input_file):
	originated_prefixes = []
	f = open(input_file, 'r')
	for line in f:
		splitted_line = line.split()
		prefix = splitted_line[0]
		originated_prefixes.append(prefix)
	f.close()
	return originated_prefixes

def output_configuration(bgp_topology):
	'''Produces a BGPSim config given a topology'''

	header = '''! BGP config

'''
	
	footer = '''
route-map from-cust permit
 set community 1
 set local-preference 100

route-map from-peer permit
 set community 2
 set local-preference 75

route-map from-provider permit
 set community 3
 set local-preference 50

route-map no-provider-peer-redistrib deny
 match community-list 2:3 any
  
route-map community-strip permit
 set community none


'''
	
	config = header
	
	for i, node in enumerate(bgp_topology):
		
		config += 'router bgp %d\n' % (node)
		config += ' bgp router-id %s\n' % (str(node) + '.1')
		
		for neighbor in bgp_topology[node]:

			if bgp_topology[node][neighbor]['type'] == 1:
				config += ' neighbor %s remote-as %d cust\n' % (str(neighbor) + '.1', neighbor)
				config += ' neighbor %s advertisement-interval %d\n' % (str(neighbor) + '.1', 30)
				config += ' neighbor %s route-map from-cust in\n' % (str(neighbor) + '.1')
				config += ' neighbor %s route-map community-strip out\n' % (str(neighbor) + '.1')
				
			elif bgp_topology[node][neighbor]['type'] == 2:
				config += ' neighbor %s remote-as %d peer\n' % (str(neighbor) + '.1', neighbor)
				config += ' neighbor %s advertisement-interval %d\n' % (str(neighbor) + '.1', 30)
				config += ' neighbor %s route-map from-peer in\n' % (str(neighbor) + '.1')
				config += ' neighbor %s route-map no-provider-peer-redistrib out\n' % (str(neighbor) + '.1')
				config += ' neighbor %s route-map community-strip out\n' % (str(neighbor) + '.1')
				
			elif bgp_topology[node][neighbor]['type'] == 3:
				config += ' neighbor %s remote-as %d prov\n' % (str(neighbor) + '.1', neighbor)
				config += ' neighbor %s advertisement-interval %d\n' % (str(neighbor) + '.1', 30)
				config += ' neighbor %s route-map from-provider in\n' % (str(neighbor) + '.1')
				config += ' neighbor %s route-map no-provider-peer-redistrib out\n' % (str(neighbor) + '.1')
				config += ' neighbor %s route-map community-strip out\n' % (str(neighbor) + '.1')
				
			else:
				print 'Error: Unknown type between node %d and %d' % (node, neighbor)
				sys.exit(-1)
		
		if i!= len(bgp_topology) - 1:
			config += '\n'
	
	config += footer
	
	return config


if __name__ == "__main__":

	#if len(sys.argv) != 3:
	#	print "Usage: %s [topology_file] [simulation_input]" % (sys.argv[0])
	#	sys.exit(-1)
    #
	#bgp_topology = topology_to_graph(sys.argv[1])
	#dragon_config = output_configuration(bgp_topology)
	#output = open(sys.argv[2], 'w')
	#output.write(dragon_config)
	#output.close()
	
	#bgp_topology = get_topology_from_gitle_graph('/Users/lvanbever/Documents/workspace/ghitle/pouet.txt')
	
	#bgp_topology = nx.DiGraph()
	#bgp_topology.add_edge(0,1, type=3)
	#bgp_topology.add_edge(0,2, type=3)
	#bgp_topology.add_edge(1,3, type=3)
	#bgp_topology.add_edge(2,3, type=3)
	#bgp_topology.add_edge(2,4, type=3)
	#bgp_topology.add_edge(3,5, type=3)
	#bgp_topology.add_edge(4,5, type=3)
	#bgp_topology.add_edge(4,6, type=3)
	#
	#for (a,b) in bgp_topology.edges():
	#	bgp_topology.add_edge(b,a, type=1)
	#
	#prefixes = get_prefix_subtree()
	#
	#print prefixes
    #
	#print assign_prefixes_to_topology(bgp_topology, prefixes)
	
	test_graph = nx.DiGraph()
	
	#test_graph.add_edge(1, 2, type=1)
	#test_graph.add_edge(1, 11, type=1)
	#test_graph.add_edge(11, 4, type=1)
	#test_graph.add_edge(11, 7, type=1)
	#test_graph.add_edge(1, 3, type=1)
	#test_graph.add_edge(1, 4, type=1)
	##test_graph.add_edge(2, 5, type=1)
	##test_graph.add_edge(2, 10, type=1)
	##test_graph.add_edge(3, 8, type=1)
	##test_graph.add_edge(5, 8, type=1)
	##test_graph.add_edge(10, 8, type=1)
	#test_graph.add_edge(4, 6, type=1)
	##test_graph.add_edge(4, 7, type=1)
	##test_graph.add_edge(6, 9, type=1)
	#test_graph.add_edge(7, 9, type=1)
	#
	#cone = set()
	#recursive_cone_dfs(test_graph, 1, cone, set(), destination_nodes=[2,11,4,6,9], edge_type=1)
	#print "pouet:", cone
	
	test_graph.add_edge(1, 2)
	test_graph.add_edge(1, 3)
	test_graph.add_edge(3, 5)
	test_graph.add_edge(2, 4)
	test_graph.add_edge(4, 6)
	test_graph.add_edge(5, 6)
	
	bad_links = return_deaggregation_triggering_link(test_graph.edges(), 1, destination_nodes=[4,5])
	
	print "bad_links: %s" % (bad_links)