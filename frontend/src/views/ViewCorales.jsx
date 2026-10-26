import { useState } from 'react';

const TOPICS = [
  {
    title: '¿Qué son los corales?',
    preview: 'Son animales, no plantas ni rocas.',
    detail: 'Los corales están formados por pólipos, pequeños animales que viven en colonias. Muchos construyen estructuras de carbonato de calcio que, con el tiempo, pueden formar arrecifes.',
    tone: 'coral',
    icon: 'coral',
  },
  {
    title: '¿Por qué son animales?',
    preview: 'Se alimentan, crecen y se reproducen.',
    detail: 'Los pólipos son animales invertebrados. Capturan alimento, desarrollan tejidos especializados y pueden reproducirse de forma sexual o asexual según la especie.',
    tone: 'turquoise',
    icon: 'animal',
  },
  {
    title: '¿Qué es un arrecife?',
    preview: 'Un ecosistema construido por organismos vivos.',
    detail: 'Un arrecife coralino combina estructuras físicas y relaciones ecológicas que ofrecen refugio, alimento y espacios de reproducción para muchas especies.',
    tone: 'sky',
    icon: 'reef',
  },
  {
    title: '¿Por qué son importantes?',
    preview: 'Protegen costas y sostienen biodiversidad.',
    detail: 'Los arrecifes ayudan a amortiguar el oleaje, aportan hábitats para múltiples organismos y están relacionados con actividades económicas y culturales de comunidades costeras.',
    tone: 'mint',
    icon: 'coast',
  },
  {
    title: 'Coral, biodiversidad y ecosistema',
    preview: 'Una red de relaciones que depende del equilibrio.',
    detail: 'La estructura tridimensional del arrecife crea microhábitats. Peces, crustáceos, moluscos y otros organismos encuentran allí recursos y espacios para completar sus ciclos de vida.',
    tone: 'blue',
    icon: 'network',
  },
  {
    title: 'Datos para recordar',
    preview: 'Ideas breves para consolidar lo aprendido.',
    detail: 'El coral es un organismo vivo; el arrecife es un ecosistema. Mantener esas dos ideas conectadas ayuda a interpretar por qué cambios ambientales pueden afectar a muchas especies a la vez.',
    tone: 'gold',
    icon: 'idea',
  },
];

const CHECKS = [
  {
    question: '¿Un coral es una planta o un animal?',
    answer: 'Es un animal invertebrado formado por pólipos.',
    options: ['Una planta acuática', 'Un animal invertebrado', 'Una roca viva'],
    correct: 1,
    tone: 'turquoise',
    icon: 'animal',
    feedback: 'Correcto. Los pólipos que forman los corales son animales invertebrados.'
  },
  {
    question: '¿Qué necesita un arrecife para mantenerse?',
    answer: 'Necesita condiciones ambientales compatibles con las especies que lo construyen y lo habitan.',
    options: ['Condiciones ambientales compatibles', 'Solo agua muy profunda', 'Ausencia de otros organismos'],
    correct: 0,
    tone: 'sky',
    icon: 'reef',
    feedback: 'Correcto. El equilibrio del arrecife depende de que las condiciones permitan vivir a los organismos que lo construyen y habitan.'
  },
  {
    question: '¿Por qué un arrecife alberga tantas especies?',
    answer: 'Porque su estructura tridimensional crea refugios, fuentes de alimento y espacios de reproducción.',
    options: ['Porque ocupa todo el océano', 'Porque crea muchos microhábitats', 'Porque todas las especies viven igual'],
    correct: 1,
    tone: 'coral',
    icon: 'network',
    feedback: 'Correcto. Su estructura tridimensional crea refugios, alimento y espacios donde distintas especies pueden desarrollarse.'
  },
  {
    question: '¿Qué idea conviene recordar primero?',
    answer: 'El coral es un organismo vivo y el arrecife es un ecosistema de relaciones.',
    options: ['Coral y arrecife significan lo mismo', 'El coral es una roca marina', 'El coral es un organismo y el arrecife es un ecosistema'],
    correct: 2,
    tone: 'mint',
    icon: 'idea',
    feedback: 'Exacto. Separar estas dos ideas ayuda a entender por qué los cambios ambientales pueden afectar a muchas especies.'
  },
];

const TONES = {
  coral: { accent: '#ff8569', soft: 'rgba(255,133,105,.12)' },
  turquoise: { accent: '#5fe0d4', soft: 'rgba(95,224,212,.12)' },
  sky: { accent: '#78d7e7', soft: 'rgba(120,215,231,.12)' },
  mint: { accent: '#9be5d9', soft: 'rgba(155,229,217,.12)' },
  blue: { accent: '#9cc8dc', soft: 'rgba(156,200,220,.12)' },
  gold: { accent: '#e6c76f', soft: 'rgba(230,199,111,.12)' },
};

function Icon({ type }) {
  const props = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  };
  const paths = {
    coral: <g className="icon-coral-group">
      <path className="icon-coral-main" d="M12 20V10"/>
      <path className="icon-coral-branch branch-a" d="M12 14 8 10"/>
      <path className="icon-coral-branch branch-b" d="M12 12l4-4"/>
      <path className="icon-coral-branch branch-c" d="M8 10V6"/>
      <path className="icon-coral-branch branch-d" d="M16 8V4"/>
      <path className="icon-coral-base" d="M6 20c.6-3.7 2.2-6.1 4.7-6.9C13.5 12.3 16.2 14.4 18 20"/>
      <circle className="icon-coral-particle p1" cx="6" cy="7" r="1"/>
      <circle className="icon-coral-particle p2" cx="18" cy="11" r=".9"/>
    </g>,
    animal: <g className="icon-animal-group">
      <circle className="icon-animal-ring" cx="12" cy="12" r="7.4"/>
      <circle className="icon-animal-core" cx="12" cy="12" r="2.3"/>
      <path className="icon-animal-fin" d="M6.5 6.8 4.5 4.8"/>
      <path className="icon-animal-fin" d="m17.5 6.8 2-2"/>
      <circle className="icon-animal-dot" cx="7" cy="14" r=".8"/>
      <circle className="icon-animal-dot" cx="17" cy="14" r=".8"/>
    </g>,
    reef: <g className="icon-reef-group">
      <path className="icon-reef-wave" d="M3 18c2-3 4-3 6 0 2-3 4-3 6 0 2-3 4-3 6 0"/>
      <path className="icon-reef-branch" d="M10 14V8"/>
      <path className="icon-reef-branch" d="m10 8-2-2"/>
      <path className="icon-reef-branch" d="m10 10 3-3"/>
      <circle className="icon-reef-bubble b1" cx="18" cy="5" r=".9"/>
      <circle className="icon-reef-bubble b2" cx="20" cy="8" r=".6"/>
    </g>,
    coast: <g className="icon-coast-group">
      <path className="icon-coast-ground" d="M4 18h16"/>
      <path className="icon-coast-main" d="M5 16c1.4-2.3 3.2-3.4 5.2-3.4 2.4 0 4 1.3 5.1 3.4"/>
      <path className="icon-coast-branch" d="M9 13V8"/>
      <path className="icon-coast-branch" d="M9 8 7 6"/>
      <circle className="icon-coast-dot" cx="17" cy="9" r=".9"/>
    </g>,
    network: <g className="icon-network-group">
      <path className="icon-network-link l1" d="m7.8 8.2 2.6 6.4"/>
      <path className="icon-network-link l2" d="m16.2 8.2-2.6 6.4"/>
      <path className="icon-network-link l3" d="M8 7h8"/>
      <circle className="icon-network-node n1" cx="6" cy="7" r="2"/>
      <circle className="icon-network-node n2" cx="18" cy="7" r="2"/>
      <circle className="icon-network-node n3" cx="12" cy="17" r="2"/>
    </g>,
    idea: <g className="icon-idea-group">
      <path className="icon-idea-base" d="M9 18h6"/>
      <path className="icon-idea-base" d="M10 21h4"/>
      <path className="icon-idea-bulb" d="M8.8 15.5c-1.3-1.1-2.2-2.7-2.2-4.5A5.4 5.4 0 0 1 12 5.6a5.4 5.4 0 0 1 5.4 5.4c0 1.8-.8 3.4-2.2 4.5"/>
      <path className="icon-idea-ray r1" d="M12 3V1.5"/>
      <path className="icon-idea-ray r2" d="m5 6-1-1"/>
      <path className="icon-idea-ray r3" d="m19 6 1-1"/>
    </g>,
    pulse: <g><path d="M3 12h4l2-5 3 10 2-5h7"/></g>,
  };
  return <svg {...props} className={`corales-v19-icon-svg icon-${type}`}>{paths[type] || paths.idea}</svg>;
}

function CoralLearningAnimation() {
  return (
    <div className="corales-v16-animation" aria-label="Animación educativa de un pólipo coralino">
      <div className="corales-v16-animation-glow" />
      <span className="corales-v16-bubble b1" />
      <span className="corales-v16-bubble b2" />
      <span className="corales-v16-bubble b3" />
      <div className="corales-v16-animation-copy">
        <span>OBSERVA</span>
        <strong>Un organismo vivo</strong>
        <small>El pólipo forma parte de una comunidad mayor.</small>
      </div>
      <svg className="corales-v16-polyp" viewBox="0 0 240 210" role="presentation">
        <defs>
          <radialGradient id="polypGlow" cx="50%" cy="42%">
            <stop offset="0%" stopColor="#82efe2" stopOpacity=".46" />
            <stop offset="100%" stopColor="#82efe2" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="polypBody" x1="0" x2="1">
            <stop offset="0%" stopColor="#4fd7ca" stopOpacity=".78" />
            <stop offset="100%" stopColor="#8fe8df" stopOpacity=".92" />
          </linearGradient>
        </defs>
        <circle cx="120" cy="94" r="76" fill="url(#polypGlow)" className="polyp-pulse" />
        <g className="polyp-sway">
          <path d="M90 166c6-31 8-64 30-84 21 16 35 45 30 84" fill="url(#polypBody)" opacity=".72" />
          <path d="M122 89c-25-20-42-33-49-50M124 91c5-30 6-49 0-65M128 93c21-20 35-33 47-52M119 94C99 72 84 67 67 67M132 94c22-21 37-24 55-26" fill="none" stroke="#9af3e8" strokeWidth="4" strokeLinecap="round" />
          <circle cx="122" cy="91" r="11" fill="#b5faf2" opacity=".9" />
          {[0,1,2,3,4,5].map((i) => <circle key={i} cx={92 + i * 10} cy={112 + (i % 2) * 7} r="3.2" fill="#55ded3" opacity=".72" />)}
        </g>
        <g className="polyp-rings" fill="none" stroke="#68e4d7" strokeWidth="1.2" opacity=".32">
          <circle cx="120" cy="94" r="52" />
          <circle cx="120" cy="94" r="68" />
        </g>
      </svg>
      <div className="corales-v16-animation-tags">
        <span><i /> captura alimento</span>
        <span><i /> simbiosis</span>
        <span><i /> crecimiento</span>
      </div>
    </div>
  );
}

export default function ViewCorales() {
  const [openTopic, setOpenTopic] = useState(null);
  const [quizIndex, setQuizIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [quizScore, setQuizScore] = useState(0);
  const [quizAnswered, setQuizAnswered] = useState(false);

  const quizItem = CHECKS[quizIndex];

  const chooseOption = (index) => {
    if (quizAnswered) return;
    setSelectedOption(index);
  };

  const checkAnswer = () => {
    if (selectedOption === null || quizAnswered) return;
    const correct = selectedOption === quizItem.correct;
    if (correct) setQuizScore((score) => score + 1);
    setQuizAnswered(true);
  };

  const nextQuestion = () => {
    const next = (quizIndex + 1) % CHECKS.length;
    setQuizIndex(next);
    setSelectedOption(null);
    setQuizAnswered(false);
  };

  const restartQuiz = () => {
    setQuizIndex(0);
    setSelectedOption(null);
    setQuizAnswered(false);
    setQuizScore(0);
  };

  return (
    <section className="corales-page-v17">
      <div className="corales-shell-v17">
        <header className="corales-v17-hero">
          <div className="corales-v17-hero-copy">
            <div className="corales-kicker-v15"><span /> EDUCACIÓN MARINA</div>
            <h1>Conoce los <em>Corales</em></h1>
            <p>Descubre qué hace extraordinarios a estos organismos. Explora una idea a la vez y conecta lo aprendido con el equilibrio del arrecife.</p>
            <div className="corales-v17-hero-note">
              <span className="corales-v17-note-dot" />
              <span>Aprende por capas: una idea, una relación y una pregunta a la vez.</span>
            </div>
          </div>
          <CoralLearningAnimation />
        </header>

        <div className="corales-v17-learning-path" aria-label="Ruta de aprendizaje">
          {['Conoce', 'Comprende', 'Relaciona', 'Recuerda'].map((step, index) => (
            <div className={`corales-v17-path-step ${index === 0 ? 'active' : ''}`} key={step}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <b>{step}</b>
              {index < 3 && <i />}
            </div>
          ))}
        </div>

        <section className="corales-v16-section">
          <div className="corales-section-head-v15 corales-v17-section-head">
            <div>
              <span>PRIMERA CAPA</span>
              <h2>Construye una visión del arrecife</h2>
            </div>
            <p>Explora una idea a la vez. Abre una carta y profundiza sin perder el hilo.</p>
          </div>

          <div className="corales-v17-topic-grid">
            {TOPICS.map((item, index) => {
              const open = openTopic === index;
              const tone = TONES[item.tone];
              return (
                <button
                  key={item.title}
                  type="button"
                  className={`corales-v17-topic-card ${open ? 'is-open' : ''}`}
                  onClick={() => setOpenTopic(open ? null : index)}
                  style={{ '--accent': tone.accent, '--soft': tone.soft, '--delay': `${index * 70}ms` }}
                  aria-expanded={open}
                >
                  <span className="corales-v17-card-number">0{index + 1}</span>
                  <span className="corales-v17-icon" aria-hidden="true"><Icon type={item.icon} /></span>
                  <strong>{item.title}</strong>
                  <small>{item.preview}</small>
                  <span className="corales-v17-card-spacer" />
                  <span className="corales-v17-card-action">{open ? 'Cerrar explicación' : 'Abrir explicación'}</span>
                  {open && <span className="corales-v17-card-detail">{item.detail}</span>}
                  <span className="corales-v17-card-line" />
                </button>
              );
            })}
          </div>
        </section>

        <section className="corales-v16-section corales-v16-recall corales-v21-game">
          <div className="corales-section-head-v15 corales-v17-section-head corales-v21-game-head">
            <div>
              <span>SEGUNDA CAPA</span>
              <h2>Pon a prueba tu memoria</h2>
            </div>
            <p>Elige una respuesta, comprueba tu idea y avanza. La meta es conectar conceptos, no memorizar de golpe.</p>
          </div>

          <div className="corales-v21-game-shell">
            <div className="corales-v21-progress">
              <div className="corales-v21-progress-meta">
                <span>DESAFÍO {String(quizIndex + 1).padStart(2, '0')} / {String(CHECKS.length).padStart(2, '0')}</span>
                <strong>{quizScore} correctas</strong>
              </div>
              <div className="corales-v21-progress-track">
                <span style={{ width: `${((quizIndex + (quizAnswered ? 1 : 0)) / CHECKS.length) * 100}%` }} />
              </div>
            </div>

            <div className="corales-v21-question" style={{ '--accent': TONES[quizItem.tone].accent, '--soft': TONES[quizItem.tone].soft }}>
              <div className="corales-v21-question-icon"><Icon type={quizItem.icon} /></div>
              <div className="corales-v21-question-copy">
                <span className="corales-v21-question-label">ELIGE LA MEJOR RESPUESTA</span>
                <h3>{quizItem.question}</h3>
                <p>Piensa primero y después selecciona una opción.</p>
              </div>
            </div>

            <div className="corales-v21-options" role="group" aria-label="Opciones de respuesta">
              {quizItem.options.map((option, index) => {
                const isSelected = selectedOption === index;
                const isCorrect = quizAnswered && index === quizItem.correct;
                const isWrong = quizAnswered && isSelected && index !== quizItem.correct;
                return (
                  <button
                    key={option}
                    type="button"
                    className={`corales-v21-option ${isSelected ? 'is-selected' : ''} ${isCorrect ? 'is-correct' : ''} ${isWrong ? 'is-wrong' : ''}`}
                    onClick={() => chooseOption(index)}
                    aria-pressed={isSelected}
                    disabled={quizAnswered}
                  >
                    <span className="corales-v21-option-index">{String.fromCharCode(65 + index)}</span>
                    <span>{option}</span>
                    <i />
                  </button>
                );
              })}
            </div>

            <div className="corales-v21-game-footer">
              <div className={`corales-v21-feedback ${quizAnswered ? 'is-visible' : ''} ${selectedOption === quizItem.correct ? 'is-correct' : 'is-wrong'}`}>
                {quizAnswered ? quizItem.feedback : 'Selecciona una opción para continuar.'}
              </div>
              <div className="corales-v21-game-actions">
                {!quizAnswered ? (
                  <button type="button" className="corales-v21-primary" onClick={checkAnswer} disabled={selectedOption === null}>Comprobar respuesta</button>
                ) : (
                  <>
                    <button type="button" className="corales-v21-secondary" onClick={restartQuiz}>Reiniciar</button>
                    <button type="button" className="corales-v21-primary" onClick={nextQuestion}>{quizIndex === CHECKS.length - 1 ? 'Volver a empezar' : 'Siguiente desafío'} →</button>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="corales-v17-takeaway">
          <div className="corales-v17-takeaway-icon"><Icon type="pulse" /></div>
          <div>
            <span>PARA RECORDAR</span>
            <strong>El coral es un organismo vivo; el arrecife es un ecosistema de relaciones.</strong>
          </div>
        </section>
      </div>
    </section>
  );
}
