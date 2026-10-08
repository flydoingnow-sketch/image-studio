#!/bin/zsh
if curl -fsS -X POST -H 'X-Hasu-Client: studio' http://127.0.0.1:8769/api/shutdown; then
 echo '\n工作台已停止。下次从应用程序打开「影像工作台」即可。'
else
 echo '\n未能停止：工作台可能未运行，或仍有任务在执行。'
fi
read 'reply?按回车键结束。'
