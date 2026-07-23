import axios from 'axios';
import { getEnv } from '../utils/env';

// TODO: 后续 PR 完善类型 - Deepseek 聊天补全响应结构
export interface DeepseekMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

// TODO: 后续 PR 完善类型 - Deepseek 配置字段
export interface DeepseekApiConfig {
    apiKey?: string;
    apiEndpoint?: string;
    model?: string;
}

export interface DeepseekChatCompletionParams {
    messages: DeepseekMessage[];
    temperature?: number;
    stream?: boolean;
}

interface InternalConfig {
    apiKey: string;
    apiEndpoint: string;
    model: string;
}

let currentConfig: InternalConfig = {
    apiKey: getEnv('VITE_DEEPSEEK_API_KEY', ''),
    apiEndpoint: getEnv('VITE_DEEPSEEK_ENDPOINT', 'https://api.deepseek.com/v1'),
    model: 'deepseek-chat',
};

export const setApiProvider = (config: DeepseekApiConfig): void => {
    currentConfig = { ...currentConfig, ...config } as InternalConfig;
};

export const getApiConfig = (): InternalConfig => currentConfig;

export const createClient = (config?: DeepseekApiConfig) => {
    if (!config || !config.apiEndpoint || !config.apiKey) {
        return {
            chat: {
                completions: {
                    create: async (): Promise<unknown> => ({
                        choices: [{ message: { content: 'Deepseek API未配置' } }],
                    }),
                },
            },
        };
    }

    const client = axios.create({
        baseURL: currentConfig.apiEndpoint,
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${currentConfig.apiKey}`,
        },
    });

    return {
        chat: {
            completions: {
                create: async (params: DeepseekChatCompletionParams): Promise<unknown> => {
                    const response = await client.post('/chat/completions', {
                        model: currentConfig.model,
                        messages: params.messages,
                        temperature: params.temperature || 0.7,
                        stream: params.stream || false,
                    });

                    if (response.status !== 200) {
                        throw new Error(`API请求失败: ${response.status} ${response.statusText}`);
                    }

                    return response.data;
                },
            },
        },
    };
};