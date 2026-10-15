When run `git` the commands are listed like this:

```
usage: git [-v | --version] [-h | --help] [-C <path>] [-c <name>=<value>]
           [--exec-path[=<path>]] [--html-path] [--man-path] [--info-path]
           [-p | --paginate | -P | --no-pager] [--no-replace-objects] [--no-lazy-fetch]
           [--no-optional-locks] [--no-advice] [--bare] [--git-dir=<path>]
           [--work-tree=<path>] [--namespace=<name>] [--config-env=<name>=<envvar>]
           <command> [<args>]

These are common Git commands used in various situations:

start a working area (see also: git help tutorial)
   clone      Clone a repository into a new directory
   init       Create an empty Git repository or reinitialize an existing one

work on the current change (see also: git help everyday)
   add        Add file contents to the index
   mv         Move or rename a file, a directory, or a symlink
   restore    Restore working tree files
   rm         Remove files from the working tree and from the index

examine the history and state (see also: git help revisions)
   bisect     Use binary search to find the commit that introduced a bug
   diff       Show changes between commits, commit and working tree, etc
   grep       Print lines matching a pattern
   log        Show commit logs
   show       Show various types of objects
   status     Show the working tree status

grow, mark and tweak your common history
   backfill   Download missing objects in a partial clone
   branch     List, create, or delete branches
   commit     Record changes to the repository
   history    EXPERIMENTAL: Rewrite history
   merge      Join two or more development histories together
   rebase     Reapply commits on top of another base tip
   reset      Set `HEAD` or the index to a known state
   switch     Switch branches
   tag        Create, list, delete or verify tags

collaborate (see also: git help workflows)
   fetch      Download objects and refs from another repository
   pull       Fetch from and integrate with another repository or a local branch
   push       Update remote refs along with associated objects

'git help -a' and 'git help -g' list available subcommands and some
concept guides. See 'git help <command>' or 'git help <concept>'
to read about a specific subcommand or concept.
See 'git help git' for an overview of the system.
```

The ordering of the commands with descriptions is really helpful. grouping by
operation makes it easier to remember what the commands do and when to use them.

Currently when I run the foundry cli I get:

usage: foundry [-h] [--workspace WORKSPACE] [--registry REGISTRY] [--json]
               {cli,run,catalog,doc,dev,visit,gate,ledger,artifact,receipt,app,config,shape,runs,status,attach,answer,decide,start,retry,cancel,host,tui,bridge,up} ...

positional arguments:
  {cli,run,catalog,doc,dev,visit,gate,ledger,artifact,receipt,app,config,shape,runs,status,attach,answer,decide,start,retry,cancel,host,tui,bridge,up}
    cli                 CLI introspection commands
    run                 Run lifecycle commands
    catalog             Catalog index commands
    doc                 Documentation generation
    dev                 Developer workflow shortcuts
    visit               Visit lifecycle commands
    gate                Gate decision commands
    ledger              Ledger inspection commands
    artifact            Artifact publication commands
    receipt             Receipt sealing commands
    app                 Application manifest bootstrap commands
    config              Foundry registry config commands
    shape               Create a run from a shape request and advance into Shape
    runs                List workspace runs (phase, node, status, wait)
    status              Show run status (default: sole active run)
    attach              Show run snapshot and stream ledger events
    answer              Submit clarifying answers when wait.kind is user_input
    decide              Submit a decision at the active user gate
    start               Explicit Shape → Execute authorization at execute.start
    retry               Retry a recoverable halted or errored run
    cancel              Stop a run with a recorded reason
    host                Local job host control
    tui                 Textual TUI for the job host (host-only client)
    bridge              Judgment bridge for FOUNDRY_AGENT_HTTP_URL
    up                  Start or reconcile bridge and host for this workspace

options:
  -h, --help            show this help message and exit
  --workspace WORKSPACE
                        Application repository root
  --registry REGISTRY   Foundry bundle root (.cursor/foundry)
  --json                Emit JSON response envelope


  It's pretty close but collecting into a flow order and group would make it
  clearer to know when to run things.