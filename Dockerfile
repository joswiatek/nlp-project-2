FROM python:3

RUN apt-get update

RUN apt-get -y install vim
RUN apt-get -y install graphviz

# Install OpenJDK-8
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk && \
    apt-get install -y ant && \
    apt-get clean;

# Fix certificate issues
RUN apt-get update && \
    apt-get install ca-certificates-java && \
    apt-get clean && \
    update-ca-certificates -f;

# Setup JAVA_HOME -- useful for docker commandline
ENV JAVA_HOME /usr/lib/jvm/java-8-openjdk-amd64/
RUN export JAVA_HOME

RUN pip install --upgrade pip
RUN pip --version

RUN pip install spacy
RUN python -m spacy download en

COPY neo4j-community-3.5.3-unix.tar.gz /
RUN tar xf /neo4j-community-3.5.3-unix.tar.gz && rm -f /neo4j-community-3.5.3-unix.tar.gz

CMD bash
