docker:
	docker run -it -v $(PWD):/root -w /root jswiatek/nlp-project-2
	@# Not sure why this won't work for neo4j
	@#docker run -it --network="host" -p 7474:7474 -v $(PWD):/root/host-dir -w /root jswiatek/nlp-project-2

setup-tools:
	if [ ! -d "neo4j-community-3.5.3" ] ; then wget -O neo4j-community-3.5.3-unix.tar.gz https://neo4j.com/artifact.php?name=neo4j-community-3.5.3-unix.tar.gz && tar xf neo4j-community-3.5.3-unix.tar.gz && rm neo4j-community-3.5.3-unix.tar.gz; fi
	if [ ! -d "Stanford-OpenIE-Python" ] ; then git clone https://github.com/philipperemy/Stanford-OpenIE-Python.git; fi
	if [ ! -d "neuralcoref" ] ; then git clone https://github.com/huggingface/neuralcoref; fi
