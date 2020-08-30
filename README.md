### “Worker” para pruebas de la cátedra, v3: _less is more_

Este rama contiene una Github Action que corre `make -k` con las dependencias especificadas en el archivo packages.txt. Se usa desde algo2_skel para correr las pruebas cada vez que se cambian.

El antiguo `corrector.py` fue [integrado][i1] en [el sistema de entregas][algo2_entregas]; `worker.py` sigue existiendo en la rama _master_, y también fue [integrado][i2] en [dato/sisyphus].

[dato/sisyphus]: https://github.com/dato/sisyphus
[algo2_entregas]: https://github.com/algoritmos-rw/algo2_sistema_entregas
[i1]: https://github.com/algoritmos-rw/algo2_sistema_entregas/commit/6eb674b46e
[i2]: https://github.com/dato/sisyphus/commit/0703e9cf22b6142330d1b415a1b06796f
