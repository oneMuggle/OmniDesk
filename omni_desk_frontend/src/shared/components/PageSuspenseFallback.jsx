import { Spin } from 'antd';

/** 路由级 lazy 加载的占位组件。 */
export default function PageSuspenseFallback() {
    return (
        <div
            style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '60vh',
            }}
        >
            <Spin size="large" tip="加载中..." />
        </div>
    );
}
