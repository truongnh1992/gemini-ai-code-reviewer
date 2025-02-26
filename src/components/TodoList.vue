<template>
  <div class="todo-list">
    <h1>{{ title }}</h1>
    <div class="input-container">
      <input 
        type="text" 
        v-model="newTodo" 
        @keyup.enter="addTodo"
        placeholder="Add a new task..."
      />
      <button @click="addTodo">Add</button>
    </div>
    <ul class="todo-items">
      <li 
        v-for="(todo, index) in todos" 
        :key="index"
        :class="{ completed: todo.completed }"
      >
        <input 
          type="checkbox" 
          v-model="todo.completed"
        />
        <span>{{ todo.text }}</span>
        <button @click="removeTodo(index)">Delete</button>
      </li>
    </ul>
    <div class="todo-stats">
      <p>{{ remainingTodos }} items left</p>
      <button @click="clearCompleted">Clear completed</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'TodoList',
  data() {
    return {
      title: 'My Todo List',
      newTodo: '',
      todos: [],
      // This variable is unused and could be flagged in a code review
      unusedVar: 'This is not used anywhere',
    }
  },
  computed: {
    remainingTodos() {
      return this.todos.filter(todo => !todo.completed).length
    }
  },
  methods: {
    addTodo() {
      if (this.newTodo.trim()) {
        this.todos.push({
          text: this.newTodo,
          completed: false
        })
        this.newTodo = ''
      }
    },
    removeTodo(index) {
      this.todos.splice(index, 1)
    },
    clearCompleted() {
      this.todos = this.todos.filter(todo => !todo.completed)
    }
  },
  // Potential security issue: using localStorage without sanitization
  mounted() {
    const savedTodos = localStorage.getItem('todos')
    if (savedTodos) {
      this.todos = JSON.parse(savedTodos)
    }
  },
  // Potential performance issue: watching the entire todos array
  watch: {
    todos: {
      handler() {
        localStorage.setItem('todos', JSON.stringify(this.todos))
      },
      deep: true
    }
  }
}
</script>

<style scoped>
.todo-list {
  max-width: 500px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}

.input-container {
  display: flex;
  margin-bottom: 20px;
}

input[type="text"] {
  flex-grow: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px 0 0 4px;
}

button {
  padding: 10px 15px;
  background-color: #4caf50;
  color: white;
  border: none;
  cursor: pointer;
}

.input-container button {
  border-radius: 0 4px 4px 0;
}

ul.todo-items {
  list-style-type: none;
  padding: 0;
}

li {
  display: flex;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #eee;
}

li.completed span {
  text-decoration: line-through;
  color: #888;
}

li button {
  margin-left: auto;
  background-color: #f44336;
  padding: 5px 10px;
  font-size: 12px;
}

.todo-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
}

.todo-stats button {
  background-color: #2196f3;
}
</style>