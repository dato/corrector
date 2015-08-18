/*
 * Setgid wrapper para worker.py. Ejecuta la imagen de Docker
 * como nobody:nogroup.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define DOCKER_IMAGE "corrector/worker"

/* El wrapper pasa los argumentos que recibe al worker. Por eso esta lista
 * estática la convertimos a dinámica con memcpy() en main().
 */
static const char *const baseCmd[] = {
  "docker", "run", "--rm", "--interactive",
  "--net", "none", "--env", "LANG=C.UTF-8",
  "--user", "nobody:nogroup", DOCKER_IMAGE,
};

int main(int argc, char *argv[]) {
  const int len = sizeof(baseCmd) / sizeof(char*);
  char *cmd[len + argc];

  memcpy(cmd, baseCmd, sizeof(baseCmd));
  memcpy(cmd + len, argv + 1, argc * sizeof(char*)); // Copia argumentos + NULL.

  execv("/usr/bin/docker", cmd);
  perror("Error en execv()");
  return -1;
}
