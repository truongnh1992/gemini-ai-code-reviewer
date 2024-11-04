# Just a dummy Dockerfile to test the code-reviewer-action
FROM node:10

# Create app directory
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Install NPM
COPY package.json /usr/src/app/
RUN npm install

RUN echo Password is `cat /cfg/password.txt`

# Bundle app source
COPY . /usr/src/app
EXPOSE 8808

CMD ["npm","start"]