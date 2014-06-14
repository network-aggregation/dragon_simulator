#include <stddef.h> /* NULL */
#include <stdio.h> /* sprintf, fprintf, stderr */
#include <stdint.h> /* int32_t */
#include <stdlib.h> /* free, atol, calloc */
#include <string.h> /* memcpy, strchr, strlen */
#include <sys/types.h> /* BSD: for inet_addr */

#include "binary_tree.h"

void destroy_tree (prefix_t *root)
{
  if (root) {
    destroy_tree(root->children[0]);
    destroy_tree(root->children[1]);
    free(root);
  }
}

char *
prefix_to_str (prefix_t *prefix)
{
  u_char *a;
  char *buff;
  a = prefix_touchar (prefix);
  buff = malloc(sizeof(char)*(200));
  sprintf(buff, "%d.%d.%d.%d/%d", a[3], a[2], a[1], a[0], prefix->mask);
  return (buff);
}

void ip_str_to_int (char * ip_str, int32_t *ip, int32_t *mask)
{
  char *cp;
  char* buff = malloc(16);
  unsigned char bytes[4];
  int bitlen;
  int i=0;
  char save[1024];
  
  if ((cp = strchr(ip_str, '/')) != NULL) {
    bitlen = atol(cp + 1);
  }
  *mask = bitlen;
	memcpy (save, ip_str, cp - ip_str);
	save[cp - ip_str] = '\0';
	ip_str = save;
  
  buff = strtok(ip_str,".");
  while (buff != NULL)
  {
    bytes[i] = (unsigned char)atoi(buff);
    buff = strtok(NULL,".");
    i++;
   }
  free(buff);
  *ip = (bytes[0] << 24) | (bytes[1] << 16) | (bytes[2] << 8) | (bytes[3] << 0);
}

prefix_t *new_prefix(int32_t ip, int32_t mask)
{
  prefix_t *prefix;
  prefix = calloc(1, sizeof *prefix);
  prefix->prefix = ip;
  prefix->mask = mask;
  prefix->parent = NULL;
  prefix->children[0] = NULL;
  prefix->children[1] = NULL;
  prefix->phi = 4;
  prefix->route_type = 4;
  prefix->covered_prefixes = 1;
#ifdef BINARY_DEBUG
  fprintf (stderr, "adding new prefix to tree: %s\n", prefix_to_str(prefix));
#endif /* BINARY_DEBUG */
	return prefix;
}

prefix_t * insert(prefix_t *root, int32_t ip, int32_t mask) {
  int i, bit, construct = 0;
  prefix_t *p = root;
  //fprintf(stdout, "inserting ip:%u into ip_root:%u with mask:%u\n", ip, root->prefix, mask);
  for (i=0; i<mask; i++){
    bit = (ip >> (31-i)) & 1;
    if(p->children[bit] == NULL){
      construct = 1;
    }
    if(construct){
      if(bit){
          //fprintf(stdout, "ip:%u--bit:%u ORing %u at pos:%d\n", ip, bit, p->prefix, (31-i));
          p->children[bit] = new_prefix(p->prefix | (1<<(31-i)), p->mask+1);
      } else {
          //fprintf(stdout, "ip:%u--bit:%u ANDing %u at pos:%d\n", ip, bit, p->prefix, (31-i));
          p->children[bit] = new_prefix(p->prefix & ~(1<<(31-i)), p->mask+1);
      }
      p->children[bit]->parent = p;
    }
    p=p->children[bit];
  }
  return p;
}

void print_list(Node *list) {
	if (list == NULL) {
		fprintf(stdout, "List is empty\n");
	} else {
		Node *cur = list;
		while (cur != NULL){
			fprintf(stdout, "Elem:%s/type:%d\n", cur->ip, cur->type);
			cur = cur->next;
		}
	}
}

Node* create_node(char *ip, int type)
{
	Node* node = (Node*) malloc(sizeof(Node));
	node->ip = ip;
	node->type = type;
	node->next = NULL;
	return node;
}

void insert_end(Node **list, char *ip, int type) {	
	if (*list == NULL) {
		*list = create_node(ip, type);
	} else {
		Node *cur = *list;
		while (cur->next != NULL){
			cur = cur->next;
		}
		cur->next = create_node(ip, type);
	}
}

void
inorder_traversal(prefix_t *prefix, void_fn_t func)
{
    if (prefix->children[0]) {
        inorder_traversal(prefix->children[0], func);
    }

    func(prefix);
	
    if (prefix->children[1]) {
        inorder_traversal(prefix->children[1], func);
    }
}

void
preorder_traversal(prefix_t *prefix, void_fn_t func)
{
    func(prefix);

    if (prefix->children[0]) {
        preorder_traversal(prefix->children[0], func);
    }
    
    if (prefix->children[1]) {
        preorder_traversal(prefix->children[1], func);
    }
}

void
postorder_traversal(prefix_t *prefix, void_fn_t func)
{
    if (prefix->children[0]) {
        postorder_traversal(prefix->children[0], func);
    }
    
    if (prefix->children[1]) {
        postorder_traversal(prefix->children[1], func);
    }

    func(prefix);
}

void
postorder_traversal_with_state(prefix_t *prefix, void_fn_t func, Node **list)
{
    if (prefix->children[0]) {
        postorder_traversal_with_state(prefix->children[0], func, list);
    }
    
    if (prefix->children[1]) {
        postorder_traversal_with_state(prefix->children[1], func, list);
    }

    func(prefix, list);
}
