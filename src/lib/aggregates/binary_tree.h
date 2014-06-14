#include <stdint.h> /* int32_t */

//#define BINARY_DEBUG 1
#define prefix_touchar(prefix) ((u_char *)&(prefix)->prefix)

typedef void (*void_fn_t)();

typedef struct _prefix_t {
  int32_t prefix;
  int32_t mask;
  struct _prefix_t *parent;
  struct _prefix_t *children[2];
  int route_type;
  int phi;
  int covered_prefixes;
} prefix_t;

struct Node;
typedef struct Node
{
	char* ip;
	int type;
	struct Node* next;
} Node;

Node* create_node(char *ip, int type);
void insert_end(Node **list, char *ip, int type);
void print_list(Node *list);

void destroy_tree (prefix_t *root);
prefix_t *insert(prefix_t *root, int32_t ip, int32_t mask);
prefix_t *new_prefix(int32_t ip, int32_t mask);
char *prefix_to_str (prefix_t *prefix);
void ip_str_to_int (char * ip_str, int32_t *ip, int32_t *mask);

/* Traversals */
void inorder_traversal (prefix_t *prefix, void_fn_t func);
void preorder_traversal (prefix_t *prefix, void_fn_t func);
void postorder_traversal (prefix_t *prefix, void_fn_t func);
void postorder_traversal_with_state(prefix_t *prefix, void_fn_t func, Node **list);