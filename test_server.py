import pytest
import requests
import subprocess
import time
import os

# Конфигурация
BASE_URL = "http://localhost:8000"
SERVER_FILE = "server.py"

@pytest.fixture(scope="module", autouse=True)
def run_server():
    # Запускаем сервер в отдельном процессе перед тестами
    if os.path.exists("tasks.txt"):
        os.remove("tasks.txt")
        
    process = subprocess.Popen(["python", SERVER_FILE])
    time.sleep(1) # Время на запуск
    
    yield
    
    # Убиваем сервер после тестов
    process.terminate()
    if os.path.exists("tasks.txt"):
        os.remove("tasks.txt")

def test_create_task():
    """ Проверка факта создания задачи """
    payload = {"title": "Test Task", "priority": "high"}
    resp = requests.post(f"{BASE_URL}/tasks", json=payload)
    
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Task"
    assert data["priority"] == "high"
    assert data["isDone"] is False
    assert "id" in data

def test_get_tasks():
    """ Проверка получения списка задач  """
    requests.post(f"{BASE_URL}/tasks", json={"title": "T1", "priority": "low"}) # Сначала создадим одну задачу
    
    resp = requests.get(f"{BASE_URL}/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_complete_task():
    """ Проверка процесса помечения задачи, как выполненной """

    #Делаем задачу
    create_resp = requests.post(f"{BASE_URL}/tasks", json={"title": "To Complete", "priority": "normal"})
    task_id = create_resp.json()["id"]
    
    # Завершаем
    resp = requests.post(f"{BASE_URL}/tasks/{task_id}/complete")
    assert resp.status_code == 200
    
    # Тестируем изменение статуса
    list_resp = requests.get(f"{BASE_URL}/tasks")
    for task in list_resp.json():
        if task["id"] == task_id:
            assert task["isDone"] is True

def test_invalid_input():
    """ Проверка валидации входных данных """

    # Неверный приоритет
    resp = requests.post(f"{BASE_URL}/tasks", json={"title": "Bad", "priority": "super-high"})
    assert resp.status_code == 400
    
    # Нет заголовка
    resp = requests.post(f"{BASE_URL}/tasks", json={"priority": "low"})
    assert resp.status_code == 400