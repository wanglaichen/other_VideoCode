const net = require('net');

const server = net.createServer((socket) => {
    console.log('client connected');
    server.on('connection', (socket) => {
        socket.write('Welcome to the snake game!\r\n');
    });
    socket.on('end', () => {
        console.log('client disconnected');
    });
});

server.listen(9111, () => {
    console.log('Server is listening on port 9111');
});

server.on('error', (error) => {
    console.error('Error:', error);
});