import axios from 'axios';
import { useAuthStore } from '../store/authStore';

export const getBackendBaseURL = () => {
    return import.meta.env.VITE_API_URL || '';
};

export const getWebSocketURL = (path: string) => {
    const apiURL = import.meta.env.VITE_API_URL || '';
    if (apiURL) {
        const formattedPath = path.startsWith('/') ? path : `/${path}`;
        const url = new URL(apiURL, window.location.href);
        const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        
        // Ensure /api prefix is present when connecting to the backend
        const basePath = url.pathname.endsWith('/api') || url.pathname.endsWith('/api/')
            ? url.pathname.replace(/\/$/, '')
            : `${url.pathname.replace(/\/$/, '')}/api`;
            
        return `${protocol}//${url.host}${basePath}${formattedPath}`;
    } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/api${path.startsWith('/') ? path : `/${path}`}`;
    }
};

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api',
});

api.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            useAuthStore.getState().logout();
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

export default api;
