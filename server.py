import http.server
import json
import os
import re
from dataclasses import dataclass, asdict

# Конфигурация
HOST = ""
PORT = 8000
DB_FILE = "tasks.txt"
PRIORITIES = {"low", "normal", "high"}

# Датакласс для описания задачи
@dataclass
class Task:
    id: int
    title: str
    priority: str
    isDone: bool = False

class TaskRepo:
    """Класс для работы с файлом задач"""
    def __init__(self, filename):
        self.filename = filename
        self.tasks = {}
        self.last_id = 0
        self._load()

    def _load(self):
        # Подгружаем данные из файла при наличии последнего
        if not os.path.exists(self.filename):
            return

        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Тривиальная валидация файлов
            if not isinstance(data, list):
                return

            for item in data:
                # Восстанавливаем объекты
                if "id" in item and "title" in item:
                    t = Task(**item)
                    self.tasks[t.id] = t
                    if t.id > self.last_id:
                        self.last_id = t.id
                        
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")

    def save(self):
        # Сохранение во временный файл
 
        tmp_file = self.filename + ".tmp"
        # Сортируем задачи по id с помощью lambda-функции и сохраняем как словари для последующего дампа в json
        data = [asdict(t) for t in sorted(self.tasks.values(), key=lambda x: x.id)]
        
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                # Сохраняем в формате json с кодировкой utf-8 баз конвертации не-ASCII символов в unicode escape последовательности 
                # и отступами немного улучшаем читаемость
                json.dump(data, f, ensure_ascii=False, indent=2) 
            os.replace(tmp_file, self.filename)
        except OSError as e:
            print(f"Не удалось сохранить файл: {e}")

    def get_all(self):
        # Возвращаем все задачи отсортированными по id
        return sorted(self.tasks.values(), key=lambda t: t.id)

    def add(self, title, priority):
        # Добавляем задачу
        self.last_id += 1
        new_task = Task(self.last_id, title, priority)
        self.tasks[self.last_id] = new_task
        self.save()
        return new_task

    def complete(self, task_id):
        # Помечаем задачу как выполненную
        if task_id in self.tasks:
            self.tasks[task_id].isDone = True
            self.save()
            return True
        return False

# Создаем экземпляр хранилища
repo = TaskRepo(DB_FILE)


#           Маршрутизация
# Список маршрутов (метод, регулярка, функция-обработчик)
ROUTES = []

def route(method, pattern):
    """Декоратор для регистрации путей API"""
    def decorator(func):
        # Компилируем регулярку один раз при запуске
        regex = re.compile(pattern)
        ROUTES.append((method, regex, func))
        return func
    return decorator

#           Хендлеры API

@route("GET", r"^/tasks$")
def get_tasks(handler, **kwargs):
    # Отдаём задачи на роуте /tasks
    tasks = [asdict(t) for t in repo.get_all()]
    handler.send_json(200, tasks)

@route("POST", r"^/tasks$")
def create_task(handler, **kwargs):
    """ Добавление задачи """
    body = handler.read_json()
    if not body:
        return handler.send_error_custom(400, "Invalid json")
    
    title = body.get("title")
    priority = body.get("priority")

    # Базовые проверки
    if not title or not isinstance(title, str):
        return handler.send_error_custom(400, "Title is required")
    
    if priority not in PRIORITIES:
        return handler.send_error_custom(400, "Priority must be low, normal or high")

    task = repo.add(title.strip(), priority)
    handler.send_json(201, asdict(task))

@route("POST", r"^/tasks/(?P<id>\d+)/complete$")
def complete_task(handler, id, **kwargs):
    """ Выполнение задачи """
    task_id = int(id)
    if repo.complete(task_id):
        handler.send_empty(200)
    else:
        handler.send_empty(404)

#           Сервер

class CustomHandler(http.server.BaseHTTPRequestHandler):
    
    def send_json(self, code, data):
        """ Отдача json-а """
        response = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def send_empty(self, code):
        """ Отдача пустого ответа """
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()
        
    def send_error_custom(self, code, message):
        """ Отдача ошибки """
        self.send_json(code, {"error": message})

    def read_json(self):
        """ Чтение json-а """
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                return None
            body = self.rfile.read(content_len)
            return json.loads(body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return None

    def _dispatch(self, method):
        """ При помощи роутинга ищем подходящий путь в списке роутов (d списке ROUTES)"""
        # Убираем параметры запроса (?limit=...) при наличии, дабы получить лишь путь
        path = self.path.split("?")[0]
        
        for r_method, r_regex, func in ROUTES:
            if r_method == method:
                match = r_regex.match(path)
                if match:
                    # Вызываем функцию, передавая self как handler и аргументы из URL
                    func(self, **match.groupdict())
                    return
        
        # Если ничего не нашли
        self.send_empty(404)

    # Переопределяем стандартные методы
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

def run():
    print(f"Сервер запущен на http://localhost:{PORT}")
    server = http.server.HTTPServer((HOST, PORT), CustomHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()

if __name__ == "__main__":
    run()