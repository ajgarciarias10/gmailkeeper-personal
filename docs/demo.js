'use strict';
// Illustrative data only. This demonstration never connects to a mailbox.
const examples = [
  {sender: 'Marca Azul', initial: 'A', color: 'blue', category: 'Promociones', brand: 'Marca Azul', unread: true},
  {sender: 'Nube Ejemplo', initial: 'N', color: 'peach', category: 'Actualizaciones', brand: 'Nube Ejemplo', unread: true},
  {sender: 'Ana · ejemplo ficticio', initial: 'A', color: 'purple', category: 'Personal', brand: null, unread: false}
];
const policy = document.getElementById('policy');
const result = document.getElementById('demo-result');

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

document.getElementById('simulate').addEventListener('click', () => {
  result.replaceChildren();
  examples.forEach((message, index) => {
    const archived = policy.value === 'all' ||
      (policy.value === 'promotions' && message.category === 'Promociones') ||
      (policy.value === 'exclude' && index !== 2);
    const row = element('div', 'demo-row');
    const head = element('div', 'demo-row-head');
    head.append(element('span', `avatar ${message.color}`, message.initial));
    head.append(element('strong', '', message.sender));
    head.append(element('span', `result-status${archived ? '' : ' kept'}`, archived ? 'Archivado' : 'En Recibidos'));
    row.append(head);
    const labels = message.brand
      ? `Archivo/${message.category} + Archivo/${message.category}/${message.brand}`
      : `Archivo/${message.category} + Archivo/Pendiente de marca`;
    row.append(element('p', '', archived ? labels : 'Fuera del alcance. Conserva sus etiquetas.'));
    row.append(element('div', 'read-note', message.unread ? 'Sigue sin leer · etiquetas anteriores conservadas' : 'Sigue leído · etiquetas anteriores conservadas'));
    result.append(row);
  });
});
