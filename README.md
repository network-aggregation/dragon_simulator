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
     gcc -c -fPIC compute_aggregates.c
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
python test_dragon.py
```
