import { App, PostMessageTransport } from '@modelcontextprotocol/ext-apps';
import { setupRentalApp } from './setup.js';
import { createSdkPort } from './sdk-port.js';
import './styles.css';

const application = new App({ name: 'Pesquisa de Aluguéis', version: '1.0.0' });
const transport = new PostMessageTransport(window.parent, window.parent);
const root = document.querySelector<HTMLElement>('#app');

if (!root) throw new Error('Elemento principal da interface não foi encontrado.');

const lifecycle = setupRentalApp(root, createSdkPort(application), () => application.connect(transport, { timeout: 180_000 }));

void lifecycle.ready.catch(() => undefined);
