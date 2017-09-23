/*
 * Setgid wrapper para worker.py. Ejecuta la imagen de Docker
 * como nobody:nogroup y sin capabilities.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef DOCKER_IMAGE
#define DOCKER_IMAGE "algoritmosrw/corrector"
#endif

#define MEM_LIM "512m"

/* El wrapper pasa los argumentos que recibe al worker. Por eso esta lista
 * estática la convertimos a dinámica con memcpy() en main().
 */
static const char *const baseCmd[] = {
  "docker", "run", "--rm", "--interactive",
  "--net", "none", "--env", "LANG=C.UTF-8",
  "--memory", MEM_LIM, "--memory-swap", MEM_LIM,
  "--user", "nobody:nogroup", "--cap-drop", "ALL",
  "--read-only", "--tmpfs", "/tmp:exec,size=75M",
  DOCKER_IMAGE,
};

int main(int argc, char *argv[]) {
  const int len = sizeof(baseCmd) / sizeof(char*);
  char *cmd[len + argc];

  memcpy(cmd, baseCmd, sizeof(baseCmd));
  memcpy(cmd + len, argv + 1,
         (unsigned) argc * sizeof(char*)); // Copia argumentos + NULL.

  execv("/usr/bin/docker", cmd);
  perror("Error en execv()");
  return -1;
}
