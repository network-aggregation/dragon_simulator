#include <stdlib.h> /* exit */
#include <stdint.h> /* int32_t */
#include <stdio.h> /* sprintf, fprintf, stderr */
#include <string.h> /* strcpy */
#include <time.h>
#include "binary_tree.h"

#define MIN_NUM_CHILDREN 2

FILE *aggregates_file;

/**
 * prints the usage instructions and exits
 */
void usage(char *filename) {
  printf("Usage: %s <ASN> <fib_directory> <results_directory>\n", filename);
  exit(0);
}

void print_prefix(prefix_t *prefix) {
  fprintf(stdout, "Prefix: %s/type: %d/phi: %d\n", prefix_to_str(prefix), prefix->route_type, prefix->phi);
}

void print_full_tree(prefix_t *prefix){
	preorder_traversal(prefix, print_prefix);
}

void assign_attributes_to_non_leaf_prefixes(prefix_t *prefix) {
    if (prefix->children[0] && prefix->children[1]) {
        if(prefix->children[0]->phi <= prefix->children[1]->phi) {
            prefix->phi = prefix->children[1]->phi;
        } else {
            prefix->phi = prefix->children[0]->phi;
        }
        prefix->covered_prefixes = prefix->children[0]->covered_prefixes + prefix->children[1]->covered_prefixes;
    }
}

void compute_aggregates(prefix_t *prefix, Node **list) {
    if (prefix->parent == NULL) {
        if(prefix->phi < prefix->route_type){
            if(prefix->covered_prefixes >= MIN_NUM_CHILDREN){
				insert_end(list, prefix_to_str(prefix), prefix->phi);
            }
        }
    } else {
        if(prefix->phi < prefix->parent->phi && prefix->phi < prefix->route_type){
            if(prefix->covered_prefixes >= MIN_NUM_CHILDREN){
				insert_end(list, prefix_to_str(prefix), prefix->phi);
            }
        }
    }
}

Node* compute_aggregates_list(prefix_t *root) {
    postorder_traversal(root, assign_attributes_to_non_leaf_prefixes);
	Node *list = NULL;
	postorder_traversal_with_state(root, compute_aggregates, &list);
	return list;
}

int read(prefix_t *root, char **argv) {
    FILE *ifp;

    int AS;
    int type;
    char pfx[100];
    char fib_input[100];
    
    strcpy(fib_input, argv[2]);
    strcat(fib_input, "/fib.");
    strcat(fib_input, argv[1]);
    
    if ((ifp = fopen(fib_input, "r")) == NULL) {
        printf("The FIB file %s doesn't seem to exist\n", fib_input);
        exit(0);
    }

    while (fscanf(ifp, "%s %d %d", pfx, &AS, &type) != EOF) {
        int ip, mask;
        ip_str_to_int(pfx, &ip, &mask);
        prefix_t *prefix = insert(root, ip, mask);
        prefix->route_type = (uint8_t) type;
        prefix->phi = (uint8_t) type;
        if(type!=0 && type!=1 && type!=2 && type!=3) {
            printf("Error when parsing FIB file. The route type should be 0, 1, 2, 3. Found: %d\n", type);
            exit(EXIT_FAILURE);
        }
    }
    
    fclose(ifp);
    return 1;
}

int main(int argc, char **argv) {
  
  if (argc != 4) {
    usage(argv[0]);
  }
  
  time_t curtime;
  struct tm *loctime;
  
  /* Get the current time. */
  curtime = time (NULL);
  /* Convert it to local time representation. */
  loctime = localtime (&curtime);
  /* Print out the date and time in the standard format. */
  fputs (asctime (loctime), stdout);
  
  /* Initialization Activities */
  //printf("Initializing Binary Tree...\n");
  prefix_t *root = new_prefix(0,0);
  
  //printf("Filling up the Binary Tree... \n");
  read(root, argv);
  
  char aggregates_output[100];
  strcpy(aggregates_output, argv[3]);
  strcat(aggregates_output, "/aggregates.");
  strcat(aggregates_output, argv[1]);
  
  aggregates_file = fopen(aggregates_output, "w+");

  /* Traversal Algorithms */
  
  //printf("Printing the tree...\n");
  //preorder_traversal(root, print_tree);
  
  //printf("Computing children per candidate...\n");
  postorder_traversal(root, assign_attributes_to_non_leaf_prefixes);
  
  //printf("Computing the minimum set of aggregates...\n");
  postorder_traversal(root, compute_aggregates);
  
  curtime = time (NULL);
  loctime = localtime (&curtime);
  fputs (asctime (loctime), stdout);
  
  /* Termination Activities */
  fclose(aggregates_file);
	destroy_tree(root);
  exit(0);
}