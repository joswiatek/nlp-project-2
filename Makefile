docker:
	docker run -it -v $(PWD):/root -w /root jswiatek/nlp-project-2
	@# Not sure why this won't work for neo4j
	@#docker run -it --network="host" -p 7474:7474 -v $(PWD):/root/host-dir -w /root jswiatek/nlp-project-2
