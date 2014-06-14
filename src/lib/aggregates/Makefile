CC := $(CROSS_COMPILE)gcc
CFLAGS := -O2 -g

OBJS := binary_tree

all: $(OBJS)

binary: binary_tree.c
	$(CC) $(CFLAGS) $^ -o $@
	
compute_aggregates: binary_tree.c compute_aggregates.c
	$(CC) $(CFLAGS) $^ -o $@

clean:
	rm -rf $(OBJS) binary_tree compute_aggregates output*

.PHONY: clean all