// src/services/api.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:3000/api', // Substitua pela URL/porta do seu backend
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;