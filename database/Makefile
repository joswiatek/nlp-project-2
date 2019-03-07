# Create a githook that automatically formats python code before commit
# Create and install libraries in a virtual enviornment
install: requirements.txt OSS/ setup.py
	- chmod +x .pre-commit.py
	- cp .pre-commit.py .git/hooks/pre-commit
	( \
		virtualenv -p python3 venv; \
		. venv/bin/activate; \
		pip3 install --upgrade pip; \
		pip3 install -r requirements.txt; \
		pwd; \
		pip3 install -e .; \
	) # Used to tell makefile to use the virtualenv shell

# Run Flask
run: OSS/ instance/
	( \
		. venv/bin/activate; \
		export FLASK_APP=OSS/__init__.py; \
		export FLASK_ENV=development; \
		flask run; \
	) # Used to tell makefile to use the virtualenv shell

# Show the routes in Flask
routes: OSS/
	( \
		. venv/bin/activate; \
		export FLASK_APP='OSS/__init__.py'; \
		flask routes; \
	) # Used to tell makefile to use the virtualenv shell

# Restart everything on the production server
restart-prod:
	systemctl stop nginx
	systemctl stop OSS
	systemctl start OSS
	systemctl start nginx

clean:
	- rm -rf .git/hooks/pre-commit
	- rm -rf *.egg*
	- rm OSS/OSS.log
	- find . | grep -E "(__pycache__|\.pyc|\.pyo)" | xargs rm -rf

# Reset all virtual enviornment data
scrub-virtualenv:
	- rm -rf ./venv
