module.exports = {
  apps: [
    {
      name: 'backend',
      script: '.venv/bin/python',
      args: 'main.py',
      cwd: '/home/guwanhua/Desktop/git/DaBoss/backend',
      exec_mode: 'fork',
      instances: 1,
      watch: false,
      max_memory_restart: '1G',
      env: {
        PYTHONPATH: '/home/guwanhua/Desktop/git/DaBoss/backend',
      },
      error_file: './logs/backend-error.log',
      out_file: './logs/backend-out.log',
      log_file: './logs/backend-combined.log',
      time: true,
    },
    {
      name: 'frontend',
      script: 'npm',
      args: 'run dev',
      cwd: '/home/guwanhua/Desktop/git/DaBoss/frontend',
      exec_mode: 'fork',
      instances: 1,
      watch: false,
      env: {
        NODE_ENV: 'development',
      },
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      log_file: './logs/frontend-combined.log',
      time: true,
    },
  ],
};
