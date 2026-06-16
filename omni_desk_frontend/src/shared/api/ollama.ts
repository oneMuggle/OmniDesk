import axios from 'axios';
import type { AxiosProgressEvent } from 'axios';
import apiClient from './apiClient';
import { logger } from '../utils/logger';

// TODO: 后续 PR 完善类型 - Ollama 配置模型(对应后端 ollama_configs 表)
export interface OllamaConfig {
    id?: number;
    name?: string;
    api_endpoint: string;
    model: string;
    temperature?: number;
    top_p?: number;
    context?: number[] | null;
}

export interface OllamaChatMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

export interface OllamaUpdatePayload {
    content: string;
    context: number[] | null;
    done: boolean;
}

export const getOllamaConfigs = () =>
    apiClient.get<OllamaConfig[]>('config/ollama-configs/');

export const addOllamaConfig = (config: Omit<OllamaConfig, 'id'>) =>
    apiClient.post<OllamaConfig>('config/ollama-configs/', config);

export const updateOllamaConfig = (id: number, config: Partial<OllamaConfig>) =>
    apiClient.put<OllamaConfig>(`config/ollama-configs/${id}/`, config);

export const deleteOllamaConfig = (id: number) =>
    apiClient.delete(`config/ollama-configs/${id}/`);

export interface OllamaChatCompletionResult {
    role: 'assistant';
    content: string;
    context: number[] | null;
    usage: { prompt_tokens: number; completion_tokens: number };
}

export const chatCompletion = async (
    config: OllamaConfig,
    messages: OllamaChatMessage[],
    onUpdate?: (payload: OllamaUpdatePayload) => void
): Promise<OllamaChatCompletionResult> => {
    const client = axios.create({
        baseURL: config.api_endpoint,
        headers: { 'Content-Type': 'application/json' },
    });

    try {
        const prompt = messages.map((m) => `${m.role}: ${m.content}`).join('\n\n');

        await client.post('generate', {
            model: config.model,
            prompt,
            stream: true,
            context: config.context || null,
            options: {
                temperature: config.temperature,
                top_p: config.top_p,
            },
        }, {
            onDownloadProgress: (progressEvent: AxiosProgressEvent) => {
                const data = progressEvent.event.currentTarget.response as string;
                const lines = data.split('\n');
                let latestContent = '';
                let latestContext: number[] | null = null;

                for (const line of lines) {
                    if (line.trim() === '') continue;
                    try {
                        const json = JSON.parse(line) as {
                            response?: string;
                            context?: number[];
                            done?: boolean;
                        };
                        if (json.response) {
                            latestContent += json.response;
                        }
                        if (json.context) {
                            latestContext = json.context;
                        }
                        if (onUpdate) {
                            onUpdate({
                                content: latestContent,
                                context: latestContext,
                                done: json.done || false,
                            });
                        }
                    } catch (e) {
                        logger.error('Error parsing stream data:', e, 'Line:', line);
                    }
                }
            },
        });

        return {
            role: 'assistant',
            content: '',
            context: null,
            usage: { prompt_tokens: 0, completion_tokens: 0 },
        };
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        throw new Error(`Ollama API请求失败: ${message}`);
    }
};

// TODO: 后续 PR 完善类型 - /api/config/ 响应结构
interface SystemConfigResponse {
    OLLAMA_ENDPOINT?: string;
    [key: string]: unknown;
}

interface OllamaTagsResponse {
    models: Array<{ name: string }>;
}

interface OllamaModelsResponse {
    // /v1/models 兼容接口响应
    data?: Array<{ id: string }>;
}

export const getModels = async (): Promise<string[]> => {
    const response = await apiClient.get<SystemConfigResponse>('config/');
    const endpoint = response.data.OLLAMA_ENDPOINT;
    if (!endpoint) {
        throw new Error('Ollama endpoint未配置');
    }
    const client = axios.create({ baseURL: endpoint });
    const res = await client.get<OllamaTagsResponse>('tags');
    return res.data.models.map((model) => model.name);
};

// eslint-disable-next-line no-unused-vars
export const setApiProvider = (config: OllamaConfig): void => {
    // Used by ApiProvider to sync config
};

export const getOllamaModelsFromEndpoint = async (
    apiEndpoint: string
): Promise<OllamaModelsResponse> => {
    const fullApiEndpoint =
        apiEndpoint.startsWith('http://') || apiEndpoint.startsWith('https://')
            ? apiEndpoint
            : `http://${apiEndpoint}`;
    const response = await axios.get<OllamaModelsResponse>(`${fullApiEndpoint}/v1/models`);
    return response.data;
};