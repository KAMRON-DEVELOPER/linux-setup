local keymap = vim.keymap

-- save and quite
keymap.set("n", "<leader>w", "<CMD>write<CR>", { desc = "save buffer" })
keymap.set("n", "<leader>q", "<CMD>quit<CR>", { desc = "close buffer" })

-- select all
vim.keymap.set("n", "==", "gg<S-v>G", { desc = "Select all" })

-- copy file name and paths
vim.keymap.set("n", "<leader>cf", '<cmd>let @+ = expand("%")<CR>', { desc = "Copy File Name" })
vim.keymap.set("n", "<leader>cp", '<cmd>let @+ = expand("%:p")<CR>', { desc = "Copy File Path" })

-- open terminal
vim.keymap.set("n", "<S-t>", function()
	vim.cmd("split")
	vim.cmd("resize 10")
	vim.cmd("terminal")
	vim.cmd("startinsert")
end, { noremap = true, silent = true })

-- window management
keymap.set("n", "<leader>sv", "<C-w>v", { desc = "Split window vertically" })
keymap.set("n", "<leader>sh", "<C-w>s", { desc = "Split window horizontally" })
keymap.set("n", "<leader>se", "<C-w>=", { desc = "Make splits equal size" })
keymap.set("n", "<leader>sx", "<CMD>close<CR>", { desc = "Close current split" })

-- resize with arrows
vim.keymap.set("n", "<C-S-Down>", ":resize +2<CR>", { desc = "Resize Horizontal Split Down" })
vim.keymap.set("n", "<C-S-Up>", ":resize -2<CR>", { desc = "Resize Horizontal Split Up" })
vim.keymap.set("n", "<C-Left>", ":vertical resize -2<CR>", { desc = "Resize Vertical Split Down" })
vim.keymap.set("n", "<C-Right>", ":vertical resize +2HCR>", { desc = "Resize Vertical Split Up" })

-- navigate vim panes better
keymap.set("n", "<c-k>", ":wincmd k<CR>", { desc = "Navigate to up pane" })
keymap.set("n", "<c-j>", ":wincmd j<CR>", { desc = "Navigate to down pane" })
keymap.set("n", "<c-h>", ":wincmd h<CR>", { desc = "Navigate to left pane" })
keymap.set("n", "<c-l>", ":wincmd l<CR>", { desc = "Navigate to right pane" })

-- tab management
keymap.set("n", "<leader>to", "<CMD>tabnew<CR>", { desc = "Open new tab" })
keymap.set("n", "<leader>tx", "<CMD>tabclose<CR>", { desc = "Close current tab" })
keymap.set("n", "<leader>tn", "<CMD>tabn<CR>", { desc = "Go to next tab" })
keymap.set("n", "<leader>tp", "<CMD>tabp<CR>", { desc = "Go to previous tab" })
keymap.set("n", "<leader>tf", "<CMD>tabnew %<CR>", { desc = "Open current buffer in new tab" })

-- increment/decrement numbers
keymap.set("n", "<leader>=", "<C-a>", { desc = "Increment number" })
keymap.set("n", "<leader>-", "<C-x>", { desc = "Decrement number" })

-- clear search highlights
keymap.set("n", "<leader>nh", ":nohl<CR>", { desc = "Clear search highlights" })

-- half page up or down
keymap.set("n", "<C-d>", "<C-d>zz")
keymap.set("n", "<C-u>", "<C-u>zz")

-- put this in your config somewhere
vim.keymap.set("n", "<leader>rr", function()
	dofile(vim.env.MYVIMRC)
	print("Reloaded init.lua")
end, { desc = "Reload Neovim config" })

vim.keymap.set("n", "<leader>R", function()
	for name, _ in pairs(package.loaded) do
		if name:match("^user") or name:match("^config") or name:match("^lsp") then
			package.loaded[name] = nil
		end
	end
	dofile(vim.env.MYVIMRC)
	print("Hard reload complete")
end, { desc = "Hard reload config" })

-- Toggle cmdheight between 0 and 1
vim.keymap.set("n", "<leader>ch", function()
	if vim.o.cmdheight == 0 then
		vim.o.cmdheight = 1
		print("Command line: visible")
	else
		vim.o.cmdheight = 0
		print("Command line: hidden")
	end
end, { desc = "Toggle command height" })



