#!/usr/bin/python
from ctypes import *

class Node(Structure):
    pass

Node._fields_ = [
	('ip', c_char_p ),
	('type', c_int ),
	('next', POINTER(Node) ),
]

class Prefix(Structure):
    pass

Prefix._fields_ = [
	('prefix', c_int ),
	('mask', c_int ),
	('parent', POINTER(Prefix) ),
	('children', POINTER(Prefix)*2 ),
	('route_type', c_int ),
	('phi', c_int ),
	('covered_prefixes', c_int )
]

cdll.LoadLibrary("./lib/aggregates/lib_aggregates.so")
lib = CDLL('./lib/aggregates/lib_aggregates.so')

#cdll.LoadLibrary("./lib_aggregates.so")
#lib = CDLL('./lib_aggregates.so')

# prefix_t *new_prefix(int32_t ip, int32_t mask);
new_prefix = lib.new_prefix
new_prefix.restype = POINTER(Prefix)
new_prefix.argtypes = [c_int, c_int]

# char *prefix_to_str (prefix_t *prefix);
prefix_to_str = lib.prefix_to_str
prefix_to_str.restype = c_char_p
prefix_to_str.argtypes = [POINTER(Prefix)]

# void ip_str_to_int (char * ip_str, int32_t *ip, int32_t *mask);
ip_str_to_int = lib.ip_str_to_int
ip_str_to_int.restype = c_void_p
ip_str_to_int.argtypes = [c_char_p, POINTER(c_int), POINTER(c_int)]

# prefix_t *insert(prefix_t *root, int32_t ip, int32_t mask)
insert = lib.insert
insert.restype = POINTER(Prefix)
insert.argtypes = [POINTER(Prefix), c_int, c_int]

# Node* compute_aggregates_list(prefix_t *root) {
compute_aggregates_list = lib.compute_aggregates_list
compute_aggregates_list.restype = POINTER(Node)
compute_aggregates_list.argtypes = [POINTER(Prefix)]

# void print_full_tree(prefix_t *prefix)
print_tree = lib.print_full_tree
print_tree.restype = c_void_p
print_tree.argtypes = [POINTER(Prefix)]

def aggregate_tree():
	return new_prefix(0,0)

def insert_pfx(root, pfx, route_type):
	cur_ip = c_int()
	cur_mask = c_int()
	cur_pfx = ip_str_to_int(pfx, byref(cur_ip), byref(cur_mask))
	pfx = insert(root, cur_ip, cur_mask)
	pfx.contents.route_type = route_type
	pfx.contents.phi = route_type

def delete_pfx(root, pfx):
	cur_ip = c_int()
	cur_mask = c_int()
	cur_pfx = ip_str_to_int(pfx, byref(cur_ip), byref(cur_mask))
	pfx = insert(root, cur_ip, cur_mask)
	pfx.contents.route_type = 4
	pfx.contents.phi = 4

def get_aggregates_pfxes(root):
	node = compute_aggregates_list(root)
	lst = []
	while node:
		node = node.contents
		if node.type == 1:
			lst.append(node.ip)
		node = node.next
	return lst

if __name__ == "__main__":
	root = aggregate_tree()
	
	insert_pfx(root, '10.0.0.0/24', 1)
	insert_pfx(root, '10.0.1.0/24', 1)
	print "pouet1", get_aggregates_pfxes(root)
	
	insert_pfx(root, '10.0.0.0/23', 1)
	insert_pfx(root, '10.0.4.0/24', 1)
	insert_pfx(root, '10.0.5.0/24', 1)
	print "pouet2", get_aggregates_pfxes(root)
	
	#delete_pfx(root, '10.0.0.0/24')
	#print "pouet3", get_aggregates_pfxes(root)