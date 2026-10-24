# Tutorial: instalar o MiKTeX e compilar LaTeX localmente

Este guia mostra como preparar um ambiente LaTeX no computador, gerar um PDF sem depender de um serviço on-line e trabalhar com um destes editores:

- **Visual Studio Code + extensão LaTeX Workshop**;
- **TeXstudio** (às vezes chamado informalmente de “LaTeX Studio”).

As instruções cobrem Windows, Linux e macOS. Os nomes exatos de alguns menus podem variar um pouco conforme a versão dos programas.

## 1. Entenda os componentes

O **MiKTeX** é a distribuição LaTeX: ela fornece os compiladores, como `pdflatex`, e os pacotes necessários para gerar documentos. O **VS Code** e o **TeXstudio** são editores; eles precisam de uma distribuição LaTeX instalada para compilar os arquivos.

Você não precisa instalar os dois editores. Escolha o que preferir. O restante deste guia explica como usar ambos com o MiKTeX.

> **Observação para macOS:** a página oficial do MiKTeX atualmente anuncia um instalador `.dmg` antigo para Intel (`x86_64`). Antes de instalar, confira os requisitos e a compatibilidade com a versão do macOS e com o processador do seu Mac. Em Macs Apple Silicon (M1/M2/M3/M4), se o instalador do MiKTeX não for compatível ou funcionar de forma instável, use uma distribuição nativa como [MacTeX/TeX Live](https://www.tug.org/mactex/) no lugar do MiKTeX. O VS Code e o TeXstudio podem trabalhar com outras distribuições LaTeX também.

## 2. Instalar o MiKTeX

Use sempre a página oficial para baixar os instaladores e consultar os sistemas compatíveis: <https://miktex.org/download>.

### 2.1 Windows

> Consulte os [pré-requisitos atuais](https://miktex.org/kb/prerequisites) antes de instalar. A página oficial atualmente lista Windows 11 x64 para o MiKTeX; não presuma que versões ou arquiteturas não listadas sejam suportadas.

1. Abra a página [Getting MiKTeX](https://miktex.org/download) e baixe o **Basic MiKTeX Installer** adequado ao seu computador.
2. Execute o arquivo baixado.
3. Aceite os termos de uso, se concordar.
4. Para um computador de uso pessoal, escolha a instalação **privada (por usuário)**. Ela costuma ser mais simples de manter do que uma instalação compartilhada para todos os usuários.
5. Selecione o tamanho de papel desejado, por exemplo **A4**.
6. Em instalação de pacotes ausentes, escolha **Ask me first** (perguntar antes) ou **Always** (instalar automaticamente). A segunda opção evita interrupções durante compilações, mas baixa pacotes da Internet quando necessário.
7. Conclua a instalação.
8. Abra o **MiKTeX Console**, entre na seção de atualizações e use **Check for updates** para verificar e instalar atualizações.

Guia oficial de instalação no Windows: <https://miktex.org/howto/install-miktex>.

Depois da instalação, feche e reabra o terminal e o editor para que eles reconheçam os executáveis do MiKTeX.

### 2.2 macOS

1. Abra <https://miktex.org/download> e verifique os requisitos do MiKTeX para macOS antes de baixar o arquivo.
2. Se o instalador for compatível com o seu Mac, baixe e abra o arquivo `.dmg`.
3. Arraste o ícone do MiKTeX para **Applications (Aplicativos)**.
4. Abra **MiKTeX Console** pelo Launchpad.
5. Complete a configuração inicial. Para uso pessoal, escolha a instalação **privada**.
6. Na seção de atualizações, procure e instale as atualizações disponíveis.
7. Ative a instalação de pacotes ausentes sob demanda, ou escolha a opção que pergunte antes de instalá-los.

Guia oficial: <https://miktex.org/howto/install-miktex-mac>.

**Verifique o `PATH`:** em uma instalação privada do MiKTeX, os executáveis podem ficar em `~/bin`. Abra o Terminal e teste:

```bash
pdflatex --version
```

Se o comando não for encontrado e o executável estiver em `~/bin`, adicione esse diretório ao `PATH`. Para o shell padrão `zsh`, use:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Se estiver usando Bash, faça isso em `~/.bashrc` em vez de `~/.zshrc`. Depois, feche e reabra o terminal e o VS Code/TeXstudio.

### 2.3 Linux

O MiKTeX oferece pacotes para algumas distribuições específicas. Confira a lista atualizada na página oficial: <https://miktex.org/download>. Os exemplos abaixo são para Ubuntu/Debian. Não use o nome de repositório de uma versão em outra versão da distribuição.

#### Ubuntu 24.04 LTS

Abra o Terminal e execute:

```bash
sudo apt-get update
sudo apt-get install curl gnupg ca-certificates
curl -fsSL https://miktex.org/download/key | sudo gpg --dearmor -o /usr/share/keyrings/miktex.gpg
echo "deb [signed-by=/usr/share/keyrings/miktex.gpg] https://miktex.org/download/ubuntu noble universe" | sudo tee /etc/apt/sources.list.d/miktex.list
sudo apt-get update
sudo apt-get install miktex
```

Para outras versões compatíveis do Ubuntu, altere `noble` conforme a tabela atual da página oficial (por exemplo, `jammy` para Ubuntu 22.04). Para Debian, use o endereço de repositório Debian e o codinome correspondente à sua versão, seguindo as instruções oficiais.

#### Fedora, Rocky Linux e openSUSE

Os comandos e endereços dos repositórios dependem da versão exata da distribuição. Abra a página oficial do MiKTeX, localize a seção da sua distribuição e copie os comandos indicados: <https://miktex.org/download>.

#### Finalizar a configuração no Linux

1. Abra o **MiKTeX Console** e conclua a configuração inicial; escolha uma instalação **privada** para uso pessoal.
2. Verifique se há atualizações e instale-as.
3. Ative a instalação automática/sob demanda de pacotes ausentes, ou escolha perguntar antes da instalação.
4. No terminal, verifique se o compilador está disponível:

```bash
pdflatex --version
```

Se você concluiu a configuração privada pela linha de comando, o MiKTeX pode instalar executáveis em `~/bin`. Se necessário, inclua esse diretório no `PATH`, conforme o exemplo para macOS acima. Se o MiKTeX Console não estiver disponível no menu de aplicativos, consulte a seção de finalização do guia oficial de instalação Linux.

## 3. Verificar se o compilador está instalado

Abra um terminal. No Windows, use PowerShell; no macOS e Linux, use Terminal. Execute:

```text
pdflatex --version
```

O comando deve mostrar informações sobre a versão do `pdfTeX`. Se aparecer uma mensagem de comando não encontrado, confira se a instalação terminou, se o MiKTeX foi configurado e se o executável está no `PATH`.

Para usar a receita padrão do LaTeX Workshop, verifique também:

```text
perl --version
latexmk --version
```

O LaTeX Workshop usa `latexmk` por padrão, e o `latexmk` precisa do **Perl**. Se esses comandos não funcionarem, veja a seção [Perl e LaTeX Workshop](#4-perl-e-latex-workshop).

## 4. Perl e LaTeX Workshop

A extensão LaTeX Workshop do VS Code usa normalmente `latexmk` para compilar documentos. A documentação oficial informa que o `latexmk` precisa do Perl. Isso é especialmente importante ao combinar LaTeX Workshop com MiKTeX, que não fornece o Perl.

- **Windows:** instale o Strawberry Perl pelo site oficial <https://strawberryperl.com/>. Use o instalador apropriado para o seu Windows e, após terminar, feche e reabra o VS Code e o terminal.
- **Ubuntu/Debian:** se o Perl não estiver instalado, execute `sudo apt-get install perl`.
- **Fedora:** se necessário, execute `sudo dnf install perl`.
- **macOS:** teste `perl --version`. Se o Perl estiver ausente, você pode instalá-lo por um gerenciador de pacotes confiável, como o Homebrew (`brew install perl`), caso já use o Homebrew.

Depois, confirme os comandos:

```text
perl --version
latexmk --version
```

Se preferir não instalar Perl, também é possível definir uma receita personalizada no LaTeX Workshop que chame `pdflatex` diretamente. Para projetos com bibliografia, referências cruzadas ou índices, uma sequência de compilação apropriada ainda pode ser necessária. A configuração da extensão está documentada em <https://github.com/James-Yu/LaTeX-Workshop/wiki/Compile>.

## 5. Criar um documento LaTeX de teste

Crie uma pasta para o projeto, por exemplo `meu-documento`, e dentro dela crie um arquivo chamado `main.tex` com este conteúdo:

```latex
\documentclass[12pt,a4paper]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[brazil]{babel}
\usepackage{amsmath}

\title{Meu primeiro documento em LaTeX}
\author{Meu nome}
\date{\today}

\begin{document}

\maketitle

Olá, mundo! Este documento foi compilado localmente.

Uma equação de exemplo:
\[
    E = mc^2
\]

\section{Conclusão}

Se este texto aparecer em um PDF, a instalação básica está funcionando.

\end{document}
```

O arquivo `.tex` é o código-fonte; a compilação gera um arquivo PDF.

## 6. Opção A — VS Code com LaTeX Workshop

### 6.1 Instalar o VS Code e a extensão

1. Instale o Visual Studio Code pelo site oficial: <https://code.visualstudio.com/>.
2. Abra o VS Code e acesse **Extensions/Extensões** na barra lateral.
3. Procure **LaTeX Workshop**, de James Yu, ou abra diretamente a página da extensão: <https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop>.
4. Clique em **Install/Instalar**.
5. Se você acabou de instalar MiKTeX ou Perl, reinicie o VS Code para atualizar as variáveis de ambiente.

### 6.2 Abrir a pasta do projeto

1. No VS Code, escolha **File > Open Folder…** e abra a pasta `meu-documento` criada anteriormente.
2. Abra o arquivo `main.tex`.
3. Salve o arquivo.
4. Abra a paleta de comandos com `Ctrl+Shift+P` no Windows/Linux ou `Cmd+Shift+P` no macOS.
5. Procure **LaTeX Workshop: Build LaTeX project** e execute o comando. Em muitas instalações, o atalho padrão para compilar é `Ctrl+Alt+B`; você também pode usar o comando da paleta.
6. Aguarde a compilação e abra o PDF usando o comando **LaTeX Workshop: View LaTeX PDF** ou o botão de visualização da extensão.

A primeira compilação pode demorar um pouco porque o MiKTeX pode baixar pacotes que estiverem faltando. Aceite a instalação dos pacotes necessários, se solicitado.

### 6.3 Se a compilação do VS Code falhar

- Confira a aba **Output/Saída** e selecione **LaTeX Workshop** para ver o registro detalhado.
- Se aparecer erro de `perl` ou `latexmk`, siga a seção [Perl e LaTeX Workshop](#4-perl-e-latex-workshop), abra um terminal novo e reinicie o VS Code.
- Se houver mensagem de pacote LaTeX ausente, permita a instalação do pacote pelo MiKTeX Console ou atualize a instalação.
- Se o VS Code não localizar `pdflatex`, teste `pdflatex --version` no terminal integrado. Se funcionar no terminal externo, mas não dentro do VS Code, feche todas as janelas do VS Code e abra-o novamente.

Referências oficiais da extensão:

- Instalação: <https://github.com/James-Yu/latex-workshop/wiki/Install>
- Compilação e receitas: <https://github.com/James-Yu/LaTeX-Workshop/wiki/Compile>

## 7. Opção B — TeXstudio

O nome oficial do editor é **TeXstudio**. Ele inclui um editor de código LaTeX e um visualizador de PDF. Assim como o VS Code, ele precisa que o MiKTeX ou outra distribuição LaTeX esteja instalado separadamente.

### 7.1 Instalar o TeXstudio

- **Windows:** baixe o instalador apropriado em <https://www.texstudio.org/> e execute-o. Em algumas versões do Windows 11, o site informa que pode ser necessário instalar o runtime do Visual C++.
- **macOS:** baixe o arquivo para a arquitetura do seu Mac na página oficial, abra o arquivo e siga as instruções para colocar o aplicativo em `Applications`.
- **Ubuntu/Debian:** tente primeiro o pacote dos repositórios da distribuição:

  ```bash
  sudo apt-get update
  sudo apt-get install texstudio
  ```

- **Outras distribuições Linux:** procure o TeXstudio no gerenciador de pacotes da sua distribuição. Se não estiver disponível, veja as opções oficiais de download, incluindo AppImage, em <https://www.texstudio.org/>.

### 7.2 Configurar e compilar

1. Abra o TeXstudio.
2. Selecione **Options > Configure TeXstudio** (em algumas versões, o menu pode estar traduzido).
3. Na seção **Build**, confira se o **Default Compiler** está definido como **PdfLaTeX**.
4. Selecione o visualizador de PDF integrado, se desejar, e confirme as configurações.
5. Abra `main.tex` e salve o arquivo.
6. Clique em **Build & View** (Compilar e visualizar). Em muitas configurações, o atalho é `F5`.
7. O TeXstudio deve compilar o documento e abrir o PDF na visualização integrada.

Se o editor disser que não encontrou `pdflatex`, volte à seção de instalação do MiKTeX e confira o `PATH`. Para um documento simples como o exemplo deste guia, o compilador PdfLaTeX é suficiente.

Site oficial: <https://www.texstudio.org/>.

## 8. Compilar pelo terminal (opcional)

Também é possível compilar sem abrir um editor. Abra o terminal dentro da pasta do projeto e execute:

```text
pdflatex main.tex
```

Se tudo der certo, o arquivo `main.pdf` será criado na pasta. Mensagens de aviso sobre referências podem exigir uma segunda compilação:

```text
pdflatex main.tex
pdflatex main.tex
```

Se Perl e `latexmk` estiverem instalados, você também pode usar:

```text
latexmk -pdf main.tex
```

O `latexmk` decide quantas vezes a compilação precisa ser executada para atualizar referências e outros arquivos auxiliares.

## 9. Problemas comuns

### `pdflatex` não é reconhecido ou não foi encontrado

Reabra o terminal após a instalação, confira se a instalação do MiKTeX foi concluída e teste o comando de novo. No macOS/Linux, confira também se o diretório `~/bin` está no `PATH`. No Windows, abra o MiKTeX Console para confirmar que a instalação está pronta.

### O MiKTeX pede um pacote que não está instalado

Permita o download do pacote quando solicitado ou ative a instalação de pacotes sob demanda no MiKTeX Console. Verifique se o computador tem acesso à Internet e atualize a instalação.

### `latexmk` falha no VS Code, mas `pdflatex` funciona

Verifique se o Perl está instalado e se `perl --version` funciona em um terminal novo. Instale o Perl, se necessário, e reinicie o VS Code. Consulte também as mensagens exibidas em **Output > LaTeX Workshop**.

### O PDF não atualiza ou as referências aparecem como `??`

Salve o arquivo e compile novamente. Referências cruzadas, numeração de seções e bibliografia podem exigir várias passagens ou uma receita de compilação específica.

### O editor abre, mas não consegue compilar

Lembre-se de que instalar o editor não instala necessariamente o compilador. Teste `pdflatex --version` fora do editor e resolva esse problema primeiro.

## 10. Links oficiais e documentação

- MiKTeX — downloads e distribuições Linux: <https://miktex.org/download>
- MiKTeX — instalação no Windows: <https://miktex.org/howto/install-miktex>
- MiKTeX — instalação no macOS: <https://miktex.org/howto/install-miktex-mac>
- MiKTeX — pré-requisitos: <https://miktex.org/kb/prerequisites>
- Visual Studio Code: <https://code.visualstudio.com/>
- LaTeX Workshop — instalação: <https://github.com/James-Yu/latex-workshop/wiki/Install>
- LaTeX Workshop — compilação: <https://github.com/James-Yu/LaTeX-Workshop/wiki/Compile>
- Strawberry Perl para Windows: <https://strawberryperl.com/>
- TeXstudio: <https://www.texstudio.org/>
- MacTeX/TeX Live (alternativa para macOS): <https://www.tug.org/mactex/>

---

**Checklist final:** MiKTeX configurado e atualizado; `pdflatex --version` funciona; para o LaTeX Workshop, Perl e `latexmk` também funcionam; `main.tex` compila e produz `main.pdf`.
