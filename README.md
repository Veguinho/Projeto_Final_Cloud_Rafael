# Projeto_Final_Cloud_Rafael
Projeto Final de Cloud - Script de criação

## Tutorial
- Para rodar o programa é necessário instalar as seguintes dependências:
```
 pip install boto3
 pip install awscli
```
 - Depois é necessário rodar o comando:
```
aws configure;
```
 Com os seguintes parâmetros referentes a sua conta da AWS: (key); (secret key); us-east-1; <null>;
- Para rodar o programa digite:  
```
python3 create_insfrastructure.py
```
- Espere todas as instâncias subirem na AWS, principalmente a instância que é controlada pelo Loadbalancer. Essa instância pertence ao security group: Loadbalancer.
  
- Para testar se o programa funcionou corretamente, altere o arquivo server_adress_test.json e substitua "{}" no campo "ip" com o DNS do Loadbalancer que foi criado na AWS na região North Virginia.

- Para rodar o teste, existem 2 comandos implementados para teste: "listar" e "adicionar". O comando "listar" retorna o banco conteúdo todo do banco de dados. O comando "adicionar" adiciona uma tarefa nova no banco de dados, com o nome "Tarefa 1".
Para rodar o teste digite:
```
python3 tarefa_test listar
```
com resultado esperado:
```
Status 200
{"lista": ["{'dificuldade': 0, 'nome': 'Tarefa 0', '_id': ObjectId('5ddd4e271c6ec0c4c3a2741f')}", "{'dificuldade': 0, 'nome': 'Tarefa 1', '_id': ObjectId('5ddd4f5fd6b73be3061fdb06')}"]}
```
ou
```
python3 tarefa_test adicionar
```
com resultado esperado:
```
Status 201
Collection(Database(MongoClient(host=['18.222.56.134:27017'], document_class=dict, tz_aware=False, connect=True), 'tarefa'), 'tarefas.1')
```
