#DRAGON Simulator Environment

Distributed Route Aggregation simulator based on SimBGP (http://www.bgpvista.com/simbgp.php)

##Requirements:

Install py-radix from https://github.com/network-aggregation/py-radix:
```
sudo apt-get install python-dev
python setup.py build
sudo python setup.py install
```

Install required Python libraries (networkx & ipaddr)
```
sudo apt-get install python-setuptools
sudo easy_install networkx
sudo easy_install ipaddr
```
Install aggregation library as a shared library:

On a MAC:
```
cd /src/lib/aggregates/
gcc -c binary_tree.c 
gcc -c compute_aggregates.c
gcc -dynamiclib -o lib_aggregates.so binary_tree.o compute_aggregates.o
```

On Linux:
```
cd /src/lib/aggregates/
gcc -c -fPIC binary_tree.c 
gcc -c -fPIC compute_aggregates.c
gcc -shared -o lib_aggregates.so binary_tree.o compute_aggregates.o
```

Run the unit tests:
```
lvanbever@ip-10-63-27-98:~/dragon_simulator/src$ python test_dragon.py 
.Running testAnycastAnnouncementOfAggregate ...
.Running testConvergenceEvent ...
.Running testConvergenceEventBGPOnly ...
.Running testFwdConsistencyFiltering ...
.Running testGenerateAggregatesForNonCoveredPrefixes ...
.Running testGenerateAggregatesForNonCoveredPrefixesWithFailure ...
.Running testGenerateAggregatesForNonCoveredPrefixesWithFailureAndBack ...
.Running testMultipleConvergenceEvent ...
.Running testMultipleLevelForwardingConsistency ...
.Running testMultipleLevelRouteConsistency ...
.Running testRouteConsistencyFiltering ...
.Running testSimpleChain ...
.Running testSimpleChainWithOneASAnnouncingParentChild ...
.Running testSimpleTriangle ...
.Running testSimpleTriangleForAggregates ...
.Running testSimpleTriangleWithFailedLink ...
.
----------------------------------------------------------------------
Ran 17 tests in 0.817s

OK
```

