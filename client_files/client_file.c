#include "../include/file.h"
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

int main (int argc, char *argv[]) {
	// ./client <server ip> <server port> <method> <file path>
	if (argc != 5) {
		printf("Uso: %s <server ip> <server port> <method> <file path>\n", argv[0]);
		return -1;
	}
	
	struct msg_request_t request;
	struct msg_reply_t reply;

	/* build request msg */
	strncpy(request.file_path, argv[4], PATH_LEN - 1);
	request.file_path[PATH_LEN - 1] = '\0';

	// GET || PUT
	if (strcmp(argv[3], "GET") == 0) request.method = FILE_GET;
	else if (strcmp(argv[3], "PUT") == 0) request.method = FILE_PUT;
	else  {
		printf("%s: metodo invalido, use GET ou PUT\n", argv[3]);
		return -1;
	}
	/* end build request msg */

	// socket
	int sfd;
	sfd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (sfd < 0) {
		perror("socket");
		return -1;
	}

	// socket address
	struct sockaddr_in saddr;
	saddr.sin_family = AF_INET;
	saddr.sin_port = htons(atoi(argv[2]));
	saddr.sin_addr.s_addr = inet_addr(argv[1]);

	// connect
	if (connect(sfd, (struct sockaddr *)&saddr, sizeof(struct sockaddr_in)) < 0) {
		perror("connect");
		return -1;
	}

	/* ---- GET ---- */
	if (request.method == FILE_GET) {
		// send
		int ns = send(sfd, &request, sizeof(struct msg_request_t), 0);
		if (ns != sizeof(struct msg_request_t)) { 
			if (ns < 0) {
				perror("send");
			}
			else {
				fprintf(stderr, "Envio incompleto\n");
			}
			close(sfd);
			return -1;
		}
		// recv
		int nr = recv(sfd, &reply, sizeof(struct msg_reply_t), 0);
		
		if (nr != sizeof(struct msg_reply_t)) {
			if (nr < 0) {
				perror("recv");
			}
			else {
				fprintf(stderr, "Resposta incompleta do servidor\n");
			}
			close(sfd);
			return -1;
		}
		if 		(reply.code == REQ_ERR) {
			fprintf(stderr, "request error: %s\n", strerror(reply.err));
			close(sfd);
			return -1;
		}
		else if (reply.code == FILE_ERR) {
			fprintf(stderr, "file error: %s\n", strerror(reply.err));
			close(sfd);
			return -1;
		}
		else if (reply.code == FILE_200)  {
			int fd = open(request.file_path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
			if (fd < 0) {
				perror("open");
				close(sfd);
				return -1;
			}

			long long bytes = 0;

			do {
				char block[BLOCK_SIZE];
				nr = recv(sfd, block, sizeof(block), 0);
				if (nr > 0) {
					int total = 0;
					/* envia o bloco para o arquivo */
					while (total < nr) {
						int nw = write(fd, block + total, nr - total);
						if (nw <= 0) {
							perror("write");
							break;
						}
						total += nw;
					}
					bytes += total;		/* atualiza o número de bytes escritos */
					if (total < nr) { 	/* bloco nao foi totalmente escrito */
						close(fd);
						close(sfd);
						return -1;		/* erro ao escrever o bloco: fecha a conexao */
					}
				}
				else if (nr < 0) {
					if (errno != EINTR) {
						perror("recv");
					}
					close(fd);
					close(sfd);
					return -1;
				}
			} while (nr > 0);
			/* nr == 0: o servidor fechou a conexao, que eh o sinal de fim do
			 * arquivo. Nao existe mais mensagem FILE_EOF no GET: ela era gravada
			 * no arquivo como se fosse dado, corrompendo o final dele. */
			printf("GET concluido: %lld bytes recebidos\n", bytes);
			close(fd);
		}
		close(sfd);
	}

	/* ---- PUT ---- */
	else if (request.method == FILE_PUT) {

	}

	return 0;
}

// 	get:
// 		send_get("GET file_path")
// 		if error:
//			handle_error()
//		else:
//			handle_response()
//

// what could cause errors?
// 	- file doesnt exist in the server
// 	- invalid file path
// both of which are handled in the server

// 	put:
//		send_put("PUT file_path")
//		if error:
//			handle_error()
//		else:
//			handle_response()

// errors can happen if:
//	- file doesn't exist in the client
//	- invalid file path
// both of which are handled in the client

// file path check is the same for both client and server
// file path must be absolute, no path traversal

// file manipulation errors: must result in operation error too

// send_get:
// build the request and send
// no need for file_path handling, the server returns the error if there is any
// if no error must receive the file and store it 
// how is the reception handled? why send/recv the file in blocks?

// send_put
// do we send a request and wait for a response before sending the file?
// send the file in blocks too, why?
// handle error in the client: file_path validity and file manipulation errors.