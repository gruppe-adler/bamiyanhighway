#ifdef WORKBENCH
/*
	EoH Tunnel Generator
	--------------------
	Grows a tunnel network out of EoH Modular Tunnel Pack pieces from a piece you've placed (an entrance, usually).
	Pieces join at the pack's own memory points, the way the pack's readme says to place them by hand.

	1. Place an entrance (or any tunnel piece or room) where the network should start, and select it.
	2. Plugins > EoH Tunnel Generator, set things up, Generate.
	3. The network goes into the active layer, every entity named EoHT_<seed>_..., with a record entity at the start
	   (EoHTunnelRecord_<seed>) that keeps the seed and settings. Select that record and use "Load from record" to get
	   them back; Clear or Regenerate with it selected to remove or rebuild that network.

	The same seed, settings, catalog and ground give the same network. Re-roll tries the next seed; Regenerate builds the
	seed in the box again. Each build replaces the one before it (this session), Clear removes it.
	New entrances still need a hole cut in the terrain (Terrain Tool, Hole), as the readme says: their places are logged.

	Following a spline: draw a SplineShapeEntity (or PolylineShapeEntity) starting at the start piece, select it (and the
	start piece, or the spline alone: then the kit piece nearest one of its ends is the start), Generate. The tunnel is
	steered along it with the usual pieces and checks and ends where it ends. Height: where the spline lies on the
	ground the tunnel keeps the usual earth cover; where its points are lowered under the ground the tunnel's centre
	line (its sockets, 1 m over its floor) follows them. A point can ask for a piece: add SP_TunnelSplinePointData
	under the point's Data (exact prefab, or a kind, and "no turns" to the next point). More splines selected, each
	starting near another: branches, with a junction where each leaves.

	Connecting entrances: select two or more entrance pieces of the kit (TT_Entry_Horizontal / TT_Entry_Incline; no spline),
	Generate. The first selected is the start and never moves. Routes are planned from it to the nearest other entrance,
	then from the nearest point of the routes so far to each further one (a junction where a branch leaves). The tunnel
	follows them with the usual pieces (rooms along the way by the usual settings); near each entrance it searches the piece
	sequences that end where that entrance's socket can meet it, and the entrance is moved to meet it, by at most the
	"Connect" settings (move, turn, height). Entrances that can't be reached are listed in the log and the result dialog.
*/
[WorkbenchPluginAttribute(name: "EoH Tunnel Generator", description: "Grow an EoH Modular Tunnel Pack network from the selected piece", wbModules: {"WorldEditor"}, awesomeFontCode: 0xF6E3)]
class SP_TunnelGenPlugin : WorldEditorPlugin
{
	// (a plain int: with a script enum as its type the plugin didn't show up in the menu)
	[Attribute("1", UIWidgets.ComboBox, "Which pieces: the EoH Modular Tunnel Pack, or our own test kit (Prefabs/Tunnels/TT: light-tight joints, rooms join tunnels directly; no light-blocking planes are added for it)", "", { ParamEnum("EoH Modular Tunnel Pack", "0"), ParamEnum("TT test kit", "1") }, category: "Seed")]
	protected int m_eKit;

	[Attribute("6", UIWidgets.EditBox, "Longest straight run, in metres, before a turn, dogleg or room must break the line of sight. 0: no limit", category: "Shape")]
	protected float m_fMaxStraightRun;

	[Attribute("3", UIWidgets.EditBox, "With a spline selected (it's followed automatically): how far, in metres, the tunnel may wander sideways off it before only pieces that bring it back are taken", category: "Spline")]
	protected float m_fSplineTolerance;

	// Connect: with two or more entrances of the kit selected (and no spline) the tunnels join them all. The first selected is the start and never moves.
	[Attribute("2", UIWidgets.EditBox, "Connect mode (2 or more entrances selected): how far, horizontally in metres, each entrance but the first may be moved so its socket meets the tunnel", category: "Connect")]
	protected float m_fDockMove;

	[Attribute("20", UIWidgets.EditBox, "Connect mode: how far, in degrees, each entrance but the first may be turned. The tunnels only turn in 90 degree steps from the first entrance's direction, so an entrance pointing further than this off that grid can't be connected", category: "Connect")]
	protected float m_fDockTurn;

	[Attribute("0.6", UIWidgets.EditBox, "Connect mode: how far, in metres, each entrance but the first may be raised or lowered. The slope piece rises 1.2 m, so 0.6 reaches any height difference", category: "Connect")]
	protected float m_fDockRise;

	// Seed
	[Attribute("0", UIWidgets.EditBox, "Layout seed. 0 picks one. After generating, the seed used is shown here", category: "Seed")]
	protected int m_iSeed;

	[Attribute("8", UIWidgets.EditBox, "Layouts to try; the best one is built (Regenerate always builds exactly the seed above)", category: "Seed")]
	protected int m_iCandidates;

	[Attribute("1", UIWidgets.CheckBox, "Put a record entity at the start with the seed and settings", category: "Seed")]
	protected bool m_bSaveRecord;

	// Size
	[Attribute("300", UIWidgets.EditBox, "Length of tunnel to aim for, in metres", category: "Size")]
	protected float m_fTargetLength;

	[Attribute("150", UIWidgets.EditBox, "Furthest any piece may be from the start, in metres", category: "Size")]
	protected float m_fMaxReach;

	[Attribute("6", UIWidgets.EditBox, "Most rooms", category: "Size")]
	protected int m_iMaxRooms;

	[Attribute("40", UIWidgets.EditBox, "Least tunnel between two rooms along one branch, in metres", category: "Size")]
	protected float m_fRoomSpacing;

	[Attribute("1", UIWidgets.CheckBox, "Allow the big rooms (20x20 m, 25x20 m)", category: "Size")]
	protected bool m_bLargeRooms;

	[Attribute("1", UIWidgets.CheckBox, "Each room at most once per network (one of each; junctions may repeat)", category: "Size")]
	protected bool m_bRoomsOnce;

	[Attribute("1", UIWidgets.CheckBox, "End dead ends in a room where one fits (an unused one), before a plain dead end", category: "Size")]
	protected bool m_bRoomAtDeadEnds;

	[Attribute("0.15", UIWidgets.Slider, "How readily a dug tunnel leads straight into a cave piece and the other way round (1 = no preference; low = caves join caves, dug joins dug, and only Brk_ pieces bridge)", "0 1 0.05", category: "Size")]
	protected float m_fThemeSwitch;

	// Shape
	[Attribute("0.5", UIWidgets.Slider, "Chance that a room's other doorframes (and a ladder's other level) lead on to side branches; otherwise they're closed off", "0 1 0.05", category: "Shape")]
	protected float m_fBranchChance;

	[Attribute("15", UIWidgets.EditBox, "Side branch length, shortest, in metres", category: "Shape")]
	protected float m_fSideBranchMin;

	[Attribute("60", UIWidgets.EditBox, "Side branch length, longest, in metres", category: "Shape")]
	protected float m_fSideBranchMax;

	[Attribute("3", UIWidgets.EditBox, "Weight of straights", category: "Shape")]
	protected float m_fStraightWeight;

	[Attribute("0.5", UIWidgets.Slider, "Share of the straights that are 7.5 m rather than 3.5 m", "0 1 0.05", category: "Shape")]
	protected float m_fLongStraightShare;

	[Attribute("1.5", UIWidgets.EditBox, "Weight of 90 degree turns", category: "Shape")]
	protected float m_fTurnWeight;

	[Attribute("0.2", UIWidgets.EditBox, "Weight of U-turns", category: "Shape")]
	protected float m_fUTurnWeight;

	[Attribute("1", UIWidgets.EditBox, "Weight of the sideways wiggles (L/R bends)", category: "Shape")]
	protected float m_fWiggleWeight;

	[Attribute("0.4", UIWidgets.EditBox, "Weight of the roof hump (standing only)", category: "Shape")]
	protected float m_fHumpWeight;

	[Attribute("0.2", UIWidgets.EditBox, "Weight of the water trap (standing only)", category: "Shape")]
	protected float m_fWaterTrapWeight;

	[Attribute("0.6", UIWidgets.Slider, "How strongly the main way keeps heading out from the start, so the network spreads instead of tangling", "0 2 0.05", category: "Shape")]
	protected float m_fHoldBearing;

	// Corridor size
	[Attribute("1", UIWidgets.EditBox, "Weight of standing corridors leaving a room", category: "Corridor size")]
	protected float m_fStandingWeight;

	[Attribute("0.6", UIWidgets.EditBox, "Weight of crouching corridors leaving a room", category: "Corridor size")]
	protected float m_fCrouchWeight;

	[Attribute("0.2", UIWidgets.EditBox, "Weight of prone (crawl) corridors leaving a room", category: "Corridor size")]
	protected float m_fProneWeight;

	// Depth
	[Attribute("1", UIWidgets.EditBox, "Least earth over any piece, in metres, measured over its real top (less right by the start piece, growing 0.6 m per piece)", category: "Depth")]
	protected float m_fMinCover;

	[Attribute("1", UIWidgets.CheckBox, "Check the earth over the tunnels. Off: pieces may go anywhere, even above the ground (for testing how they join and block light)", category: "Depth")]
	protected bool m_bCheckCover;

	[Attribute("2", UIWidgets.EditBox, "Starting from an entrance: how far the first pieces after it may stick out of the ground, in metres (0.8 m less for each piece after, until the least earth above applies). For shaping the ground round the mouth by hand", category: "Depth")]
	protected float m_fEntranceExposure;

	[Attribute("3.5", UIWidgets.EditBox, "Earth over the tunnels to aim for, in metres: slopes are chosen to keep to it as the ground rises and falls", category: "Depth")]
	protected float m_fTargetCover;

	[Attribute("1", UIWidgets.EditBox, "Weight of slopes", category: "Depth")]
	protected float m_fSlopeWeight;

	[Attribute("0.4", UIWidgets.EditBox, "Weight of climbing turns", category: "Depth")]
	protected float m_fUpTurnWeight;

	[Attribute("0.15", UIWidgets.EditBox, "Weight of the ladder piece (standing only)", category: "Depth")]
	protected float m_fLadderWeight;

	[Attribute("8", UIWidgets.EditBox, "Most changes of level (slopes, climbing turns, ladders) in the whole network", category: "Depth")]
	protected int m_iMaxLevelChanges;

	// Entrances
	[Attribute("1", UIWidgets.EditBox, "Extra entrances, as well as the one you placed", category: "Entrances")]
	protected int m_iExtraEntrances;

	[Attribute("70", UIWidgets.EditBox, "Least distance between entrances, in metres", category: "Entrances")]
	protected float m_fEntranceSpacing;

	[Attribute("1", UIWidgets.EditBox, "How far an entrance's top may be from the ground, in metres (you shape the terrain to fit afterwards)", category: "Entrances")]
	protected float m_fEntranceTolerance;

	[Attribute("1", UIWidgets.CheckBox, "Use Entrance_Floor_Staircase (standing)", category: "Entrances")]
	protected bool m_bEntranceStaircase;

	[Attribute("1", UIWidgets.CheckBox, "Use Entrance_Floor_Hole (crouching)", category: "Entrances")]
	protected bool m_bEntranceHole;

	[Attribute("1", UIWidgets.CheckBox, "Use Entrance_Rocky (crouching)", category: "Entrances")]
	protected bool m_bEntranceRocky;

	[Attribute("1", UIWidgets.CheckBox, "Use Entrance_Hill_Crawl (prone)", category: "Entrances")]
	protected bool m_bEntranceHillCrawl;

	// Output
	[Attribute("1", UIWidgets.CheckBox, "Masks where corridors meet doorways (the readme: these never line up)", category: "Output")]
	protected bool m_bMasksAtDoorways;

	[Attribute("1", UIWidgets.CheckBox, "Masks on every joint, to cover any gap and block light", category: "Output")]
	protected bool m_bMasksAtAllJoints;

	[Attribute("1", UIWidgets.CheckBox, "Keep clear of tunnel pieces already in the world", category: "Output")]
	protected bool m_bAvoidExisting;

	[Attribute("1", UIWidgets.CheckBox, "Keep clear of anything solid in the world (cliffs, rocks, buildings): each piece is tested against their real collision, so tunnels go round them or underneath", category: "Output")]
	protected bool m_bAvoidWorld;

	[Attribute("1", UIWidgets.CheckBox, "Plants and trees don't count as in the way (their collision is above ground)", category: "Output")]
	protected bool m_bIgnorePlants;

	[Attribute("1", UIWidgets.CheckBox, "A light-blocking plane (GridPlane_100x100, no collision) over each piece: the terrain doesn't block light", category: "Output")]
	protected bool m_bLightBlockers;

	[Attribute("1.5", UIWidgets.EditBox, "Light blockers: how far each plane reaches past its piece on every side, in metres, so the sun at an angle can't get past the plane's edge to a joint", category: "Output")]
	protected float m_fBlockerMargin;

	[Attribute("1", UIWidgets.CheckBox, "Dark light probes (EoH Tunnel Network's, which darken the sky's light by 22 stops) along every corridor and in every room, so no part of the tunnels is lit by the sky", category: "Output")]
	protected bool m_bDarkProbes;

	[Attribute("0.3", UIWidgets.EditBox, "Light blockers: how far under the ground they go, in metres (lower only where the tunnel roof is closer to the surface than that)", category: "Output")]
	protected float m_fBlockerDepth;

	[Attribute("0", UIWidgets.CheckBox, "Only plan and log, place nothing", category: "Output")]
	protected bool m_bDryRun;

	protected ref SP_TunnelCatalog m_Catalog;
	protected int m_iBuiltSeed = -1;		// the build Re-roll and Clear replace: its entities are named after its seed
	protected int m_iLastSeed = -1;		// the seed the last build put in the box
	protected int m_iBlockersHigh;
	protected float m_fBlockerSize;		// the light blocker plane's width at scale 1
	protected vector m_vBlockerMid;		// and where its middle is from its pivot
	protected float m_fYawSign = 1;
	protected bool m_bYawChecked;
	protected ResourceName m_sBlocker;
	protected ref array<ResourceName> m_aFoundBlockers = {};
	protected ref array<IEntity> m_aFoundPieces = {};

	//------------------------------------------------------------------------------------------------
	override void Run()
	{
		Workbench.ScriptDialog("EoH Tunnel Generator", "Select the piece to grow from (an entrance, usually), or a record entity to load its settings. Select a spline too (or only the spline, drawn from the start piece) to make the tunnel follow it.", this);
	}

	//------------------------------------------------------------------------------------------------
	protected WorldEditorAPI Api()
	{
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		if (!worldEditor)
			return null;

		return worldEditor.GetApi();
	}

	//------------------------------------------------------------------------------------------------
	protected SP_TunnelGenSettings Settings()
	{
		SP_TunnelGenSettings cfg = new SP_TunnelGenSettings();
		cfg.m_iSeed = m_iSeed;
		cfg.m_iCandidates = Math.Max(m_iCandidates, 1);
		cfg.m_fTargetLength = m_fTargetLength;
		cfg.m_fMaxReach = m_fMaxReach;
		cfg.m_iMaxRooms = m_iMaxRooms;
		cfg.m_fRoomSpacing = m_fRoomSpacing;
		cfg.m_bLargeRooms = m_bLargeRooms;
		cfg.m_bRoomsOnce = m_bRoomsOnce;
		cfg.m_bRoomAtDeadEnds = m_bRoomAtDeadEnds;
		cfg.m_fThemeSwitch = m_fThemeSwitch;
		cfg.m_fBranchChance = m_fBranchChance;
		cfg.m_fSideBranchMin = m_fSideBranchMin;
		cfg.m_fSideBranchMax = m_fSideBranchMax;
		cfg.m_fStraightWeight = m_fStraightWeight;
		cfg.m_fLongStraightShare = m_fLongStraightShare;
		cfg.m_fTurnWeight = m_fTurnWeight;
		cfg.m_fUTurnWeight = m_fUTurnWeight;
		cfg.m_fWiggleWeight = m_fWiggleWeight;
		cfg.m_fHumpWeight = m_fHumpWeight;
		cfg.m_fWaterTrapWeight = m_fWaterTrapWeight;
		cfg.m_fHoldBearing = m_fHoldBearing;
		cfg.m_fStandingWeight = m_fStandingWeight;
		cfg.m_fCrouchWeight = m_fCrouchWeight;
		cfg.m_fProneWeight = m_fProneWeight;
		cfg.m_fMinCover = m_fMinCover;
		cfg.m_bCheckCover = m_bCheckCover;
		cfg.m_fEntranceExposure = m_fEntranceExposure;
		cfg.m_fTargetCover = m_fTargetCover;
		cfg.m_fSlopeWeight = m_fSlopeWeight;
		cfg.m_fUpTurnWeight = m_fUpTurnWeight;
		cfg.m_fLadderWeight = m_fLadderWeight;
		cfg.m_iMaxLevelChanges = m_iMaxLevelChanges;
		cfg.m_iExtraEntrances = m_iExtraEntrances;
		cfg.m_fEntranceSpacing = m_fEntranceSpacing;
		cfg.m_fEntranceTolerance = m_fEntranceTolerance;
		cfg.m_bEntranceStaircase = m_bEntranceStaircase;
		cfg.m_bEntranceHole = m_bEntranceHole;
		cfg.m_bEntranceRocky = m_bEntranceRocky;
		cfg.m_bEntranceHillCrawl = m_bEntranceHillCrawl;
		cfg.m_bMasksAtDoorways = m_bMasksAtDoorways;
		cfg.m_bMasksAtAllJoints = m_bMasksAtAllJoints;
		cfg.m_bAvoidExisting = m_bAvoidExisting;
		cfg.m_bAvoidWorld = m_bAvoidWorld;
		cfg.m_bIgnorePlants = m_bIgnorePlants;
		cfg.m_bLightBlockers = m_bLightBlockers;
		cfg.m_fMaxStraightRun = m_fMaxStraightRun;
		cfg.m_iKit = m_eKit;
		cfg.m_fSplineTolerance = m_fSplineTolerance;
		cfg.m_fDockMove = m_fDockMove;
		cfg.m_fDockTurn = m_fDockTurn;
		cfg.m_fDockRise = m_fDockRise;
		return cfg;
	}

	//------------------------------------------------------------------------------------------------
	protected void ApplySettings(SP_TunnelGenSettings cfg)
	{
		m_iCandidates = cfg.m_iCandidates;
		m_fTargetLength = cfg.m_fTargetLength;
		m_fMaxReach = cfg.m_fMaxReach;
		m_iMaxRooms = cfg.m_iMaxRooms;
		m_fRoomSpacing = cfg.m_fRoomSpacing;
		m_bLargeRooms = cfg.m_bLargeRooms;
		m_bRoomsOnce = cfg.m_bRoomsOnce;
		m_bRoomAtDeadEnds = cfg.m_bRoomAtDeadEnds;
		m_fThemeSwitch = cfg.m_fThemeSwitch;
		m_fBranchChance = cfg.m_fBranchChance;
		m_fSideBranchMin = cfg.m_fSideBranchMin;
		m_fSideBranchMax = cfg.m_fSideBranchMax;
		m_fStraightWeight = cfg.m_fStraightWeight;
		m_fLongStraightShare = cfg.m_fLongStraightShare;
		m_fTurnWeight = cfg.m_fTurnWeight;
		m_fUTurnWeight = cfg.m_fUTurnWeight;
		m_fWiggleWeight = cfg.m_fWiggleWeight;
		m_fHumpWeight = cfg.m_fHumpWeight;
		m_fWaterTrapWeight = cfg.m_fWaterTrapWeight;
		m_fHoldBearing = cfg.m_fHoldBearing;
		m_fStandingWeight = cfg.m_fStandingWeight;
		m_fCrouchWeight = cfg.m_fCrouchWeight;
		m_fProneWeight = cfg.m_fProneWeight;
		m_fMinCover = cfg.m_fMinCover;
		m_bCheckCover = cfg.m_bCheckCover;
		m_fEntranceExposure = cfg.m_fEntranceExposure;
		m_fTargetCover = cfg.m_fTargetCover;
		m_fSlopeWeight = cfg.m_fSlopeWeight;
		m_fUpTurnWeight = cfg.m_fUpTurnWeight;
		m_fLadderWeight = cfg.m_fLadderWeight;
		m_iMaxLevelChanges = cfg.m_iMaxLevelChanges;
		m_iExtraEntrances = cfg.m_iExtraEntrances;
		m_fEntranceSpacing = cfg.m_fEntranceSpacing;
		m_fEntranceTolerance = cfg.m_fEntranceTolerance;
		m_bEntranceStaircase = cfg.m_bEntranceStaircase;
		m_bEntranceHole = cfg.m_bEntranceHole;
		m_bEntranceRocky = cfg.m_bEntranceRocky;
		m_bEntranceHillCrawl = cfg.m_bEntranceHillCrawl;
		m_bMasksAtDoorways = cfg.m_bMasksAtDoorways;
		m_bMasksAtAllJoints = cfg.m_bMasksAtAllJoints;
		m_bAvoidExisting = cfg.m_bAvoidExisting;
		m_bAvoidWorld = cfg.m_bAvoidWorld;
		m_bIgnorePlants = cfg.m_bIgnorePlants;
		m_bLightBlockers = cfg.m_bLightBlockers;
		m_fMaxStraightRun = cfg.m_fMaxStraightRun;
		m_eKit = cfg.m_iKit;
		m_fSplineTolerance = cfg.m_fSplineTolerance;
		m_fDockMove = cfg.m_fDockMove;
		m_fDockTurn = cfg.m_fDockTurn;
		m_fDockRise = cfg.m_fDockRise;
	}

	//------------------------------------------------------------------------------------------------
	protected bool LoadCatalog(WorldEditorAPI api, bool rebuild)
	{
		if (!m_Catalog || m_Catalog.m_iKit != m_eKit)
			m_Catalog = new SP_TunnelCatalog(m_eKit);

		if (!rebuild && !m_Catalog.m_aPieces.IsEmpty())
			return true;

		if (m_Catalog.Get(api, rebuild))
			return true;

		Workbench.Dialog("EoH Tunnel Generator", "The piece catalog couldn't be built. Is the EoH Modular Tunnel Pack a dependency of this project? See the log.");
		return false;
	}

	//================================================================================================
	// Buttons
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Generate", true)]
	protected void ButtonGenerate()
	{
		// The seed box still showing the last build's seed: a new search. A seed typed in: search from that one.
		int seed = m_iSeed;
		if (seed == m_iLastSeed)
			seed = 0;

		Generate(seed, Math.Max(m_iCandidates, 1));
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Regenerate (this seed)")]
	protected void ButtonRegenerate()
	{
		if (m_iSeed == 0)
		{
			Workbench.Dialog("EoH Tunnel Generator", "Put a seed in the Seed box first (or Generate to get one).");
			return;
		}

		Generate(m_iSeed, 1);
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Re-roll")]
	protected void ButtonReroll()
	{
		int next = m_iSeed + 1;
		if (m_iSeed == 0)
			next = 0;

		Generate(next, Math.Max(m_iCandidates, 1));
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Load from record")]
	protected void ButtonLoad()
	{
		WorldEditorAPI api = Api();
		if (!api)
			return;

		IEntityComponentSource record = SelectedRecord(api);
		if (!record)
		{
			Workbench.Dialog("EoH Tunnel Generator", "Select a tunnel record entity (EoHTunnelRecord_...) first.");
			return;
		}

		int seed;
		string settings;
		string hash;
		record.Get("m_iSeed", seed);
		record.Get("m_sSettings", settings);
		record.Get("m_sCatalogHash", hash);
		SP_TunnelGenSettings cfg = new SP_TunnelGenSettings();
		cfg.Read(settings);
		ApplySettings(cfg);
		m_iSeed = seed;
		m_iLastSeed = -1;
		m_iBuiltSeed = seed;
		string note = "";
		if (LoadCatalog(api, false) && hash != m_Catalog.m_sHash)
			note = "\n\nThe piece catalog has changed since (" + hash + " then, " + m_Catalog.m_sHash + " now): the same seed may give a different network.";

		Workbench.Dialog("EoH Tunnel Generator", string.Format("Loaded seed %1 and its settings.%2\n\nRegenerate rebuilds it in place.", seed, note));
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Clear")]
	protected void ButtonClear()
	{
		WorldEditorAPI api = Api();
		if (!api)
			return;

		IEntityComponentSource record = SelectedRecord(api);
		if (record)
			record.Get("m_iSeed", m_iBuiltSeed);

		if (m_iBuiltSeed < 0)
		{
			Workbench.Dialog("EoH Tunnel Generator", "Nothing to clear: generate first, or select a record entity.");
			return;
		}

		api.BeginEntityAction("EoH tunnels: clear");
		int removed = ClearBuild(api, m_iBuiltSeed);
		api.EndEntityAction();
		Print(string.Format("SP_TunnelGen: cleared %1 entities of build %2", removed, m_iBuiltSeed));
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Verify catalog")]
	protected void ButtonVerify()
	{
		WorldEditorAPI api = Api();
		if (!api || !LoadCatalog(api, false))
			return;

		Verify(api);
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Rebuild catalog")]
	protected void ButtonRebuild()
	{
		WorldEditorAPI api = Api();
		if (!api)
			return;

		if (LoadCatalog(api, true))
			Workbench.Dialog("EoH Tunnel Generator", string.Format("Catalog rebuilt: %1 pieces (hash %2). Written to %3", m_Catalog.m_aPieces.Count(), m_Catalog.m_sHash, m_Catalog.m_sFile));
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Close")]
	protected bool ButtonClose()
	{
		return false;
	}

	//================================================================================================
	// Generating
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	protected IEntityComponentSource SelectedRecord(WorldEditorAPI api)
	{
		if (api.GetSelectedEntitiesCount() < 1)
			return null;

		IEntitySource src = api.GetSelectedEntity(0);
		if (!src)
			return null;

		for (int c = 0; c < src.GetComponentCount(); c++)
		{
			IEntityComponentSource component = src.GetComponent(c);
			if (component && component.GetClassName() == "SP_TunnelGenRecordComponent")
				return component;
		}

		return null;
	}

	//------------------------------------------------------------------------------------------------
	//! The selected entity's prefab: the first in its line of ancestors (it, the prefab it was made from, and so on)
	//! that is a piece of the catalog; otherwise the nearest prefab name found, for the message
	protected ResourceName PrefabOf(IEntitySource src, IEntity entity, out int pieceIndex)
	{
		pieceIndex = -1;
		ResourceName first = "";
		BaseContainer ancestor = src.GetAncestor();
		for (int depth = 0; depth < 6 && ancestor; depth++)
		{
			ResourceName name = ancestor.GetResourceName();
			if (!name.IsEmpty())
			{
				if (first.IsEmpty())
					first = name;

				pieceIndex = m_Catalog.IndexOfPrefab(name);
				if (pieceIndex >= 0)
					return name;
			}

			ancestor = ancestor.GetAncestor();
		}

		if (entity && entity.GetPrefabData())
		{
			ResourceName data = entity.GetPrefabData().GetPrefabName();
			pieceIndex = m_Catalog.IndexOfPrefab(data);
			if (pieceIndex >= 0 || first.IsEmpty())
				return data;
		}

		return first;
	}

	//------------------------------------------------------------------------------------------------
	//! The piece to grow from: the selection (the first selected that isn't a spline), the start piece a selected record
	//! names, or with only splines selected, the kit's piece nearest one of their ends
	protected bool FindStart(WorldEditorAPI api, array<IEntitySource> shapes, out int pieceIndex, out vector pos, out float yaw, out IEntity startEntity)
	{
		pieceIndex = -1;
		if (api.GetSelectedEntitiesCount() < 1)
		{
			Workbench.Dialog("EoH Tunnel Generator", "Select the piece to grow from first: an entrance, a tunnel piece or a room of the chosen kit (and a spline to follow, if wanted).");
			return false;
		}

		IEntityComponentSource record = SelectedRecord(api);
		if (record)
		{
			ResourceName recordPrefab;
			record.Get("m_sStartPrefab", recordPrefab);
			record.Get("m_vStartPos", pos);
			record.Get("m_fStartYaw", yaw);
			pieceIndex = m_Catalog.IndexOfPrefab(recordPrefab);
			if (pieceIndex < 0)
			{
				Workbench.Dialog("EoH Tunnel Generator", "The record's start piece isn't in the catalog: " + recordPrefab);
				return false;
			}

			return true;
		}

		IEntitySource src;
		for (int i = 0; i < api.GetSelectedEntitiesCount(); i++)
		{
			IEntitySource selected = api.GetSelectedEntity(i);
			if (selected && !ShapeEntity.Cast(api.SourceToEntity(selected)))
			{
				src = selected;
				break;
			}
		}

		if (!src)
		{
			src = PieceNearShapes(api, shapes);
			if (!src)
			{
				Workbench.Dialog("EoH Tunnel Generator", string.Format("Only splines are selected, and no piece of the chosen kit is within %1 m of either end of one. Place the entry where the spline starts, or select it as well.", START_SEARCH));
				return false;
			}
		}

		startEntity = api.SourceToEntity(src);
		ResourceName prefab = PrefabOf(src, startEntity, pieceIndex);
		if (pieceIndex < 0 || !startEntity)
		{
			string shown = prefab;
			if (shown.IsEmpty())
				shown = "no prefab: placed from a model? Place the piece's prefab (.et) instead";

			Workbench.Dialog("EoH Tunnel Generator", "The selected entity isn't a piece of the chosen kit (" + shown + "). Check the Kit setting, and that you selected the piece itself.");
			return false;
		}

		Print("SP_TunnelGen: the selected piece is " + m_Catalog.m_aPieces[pieceIndex].m_sName + " (" + prefab + ")");

		vector mat[4];
		startEntity.GetWorldTransform(mat);
		pos = mat[3];
		yaw = SP_TunnelGrower.YawOf(mat[2]);
		if (mat[1][1] < 0.999)
			Print("SP_TunnelGen: the start piece is tilted; the network is grown level from it, so the first joint may not line up", LogLevel.WARNING);

		return true;
	}

	//================================================================================================
	// Splines
	//================================================================================================

	protected static const float START_SEARCH = 20;	// with only splines selected: how far from an end the start piece may be

	//------------------------------------------------------------------------------------------------
	//! Connect mode: the selected entities that are entrances of the kit, in selection order (not shapes; not pieces a build
	//! made, which a new build would clear). True: two or more, the first being the start and the rest "pinned".
	protected bool SelectedEntrances(WorldEditorAPI api, notnull array<ref SP_TunnelPin> pins)
	{
		for (int i = 0; i < api.GetSelectedEntitiesCount(); i++)
		{
			IEntitySource src = api.GetSelectedEntity(i);
			if (!src)
				continue;

			IEntity entity = api.SourceToEntity(src);
			if (!entity || ShapeEntity.Cast(entity))
				continue;

			int pieceIndex;
			PrefabOf(src, entity, pieceIndex);
			if (pieceIndex < 0 || m_Catalog.m_aPieces[pieceIndex].m_iKind != SP_TunnelKind.ENTRANCE)
				continue;

			string srcName = src.GetName();
			if (srcName.IndexOf("EoHT_") == 0)
			{
				Print("SP_TunnelGen: " + srcName + " was made by a build: left out of the entrances to connect", LogLevel.WARNING);
				continue;
			}

			vector mat[4];
			entity.GetWorldTransform(mat);
			SP_TunnelPin pin = new SP_TunnelPin();
			pin.m_Entity = entity;
			pin.m_Src = src;
			pin.m_iPiece = pieceIndex;
			pin.m_vPos = mat[3];
			pin.m_fYaw = SP_TunnelGrower.YawOf(mat[2]);
			pin.m_sName = srcName;
			if (pin.m_sName.IsEmpty())
				pin.m_sName = m_Catalog.m_aPieces[pieceIndex].m_sName + " at " + pin.m_vPos.ToString(false);

			if (src.GetParent())
				pin.m_sSkip = "it is inside another entity, so it can't be moved";
			else if (mat[1][1] < 0.999)
				Print("SP_TunnelGen: " + pin.m_sName + " is tilted; it is only turned about the vertical", LogLevel.WARNING);

			pins.Insert(pin);
		}

		return pins.Count() >= 2;
	}

	//------------------------------------------------------------------------------------------------
	//! A docked entrance to its new pose (its own undo step): the same keys the editor uses, coords and angleY
	protected void MoveEntrance(WorldEditorAPI api, SP_TunnelDocking dock)
	{
		if (!dock.m_Src)
			return;

		api.BeginEntityAction("EoH tunnels: dock entrance " + dock.m_sName);
		api.SetVariableValue(dock.m_Src, null, "coords", dock.m_vPos.ToString(false));
		api.SetVariableValue(dock.m_Src, null, "angleY", (dock.m_fYaw * m_fYawSign).ToString());
		api.EndEntityAction();
		Print(string.Format("SP_TunnelGen:   entrance %1 moved from %2 (yaw %3) to %4 (yaw %5)", dock.m_sName, dock.m_vFrom.ToString(false), Math.Round(dock.m_fFromYaw), dock.m_vPos.ToString(false), Math.Round(dock.m_fYaw)));
	}

	//------------------------------------------------------------------------------------------------
	//! The selected splines and polylines
	protected array<IEntitySource> SelectedShapes(WorldEditorAPI api)
	{
		array<IEntitySource> shapes = {};
		for (int i = 0; i < api.GetSelectedEntitiesCount(); i++)
		{
			IEntitySource src = api.GetSelectedEntity(i);
			if (src && ShapeEntity.Cast(api.SourceToEntity(src)))
				shapes.Insert(src);
		}

		return shapes;
	}

	//------------------------------------------------------------------------------------------------
	//! A shape's point (in its own space) in the world
	protected vector ToWorld(vector local, vector mat[4])
	{
		return mat[0] * local[0] + mat[1] * local[1] + mat[2] * local[2] + mat[3];
	}

	//------------------------------------------------------------------------------------------------
	//! The kit's piece nearest an end of one of the splines (not one a build made)
	protected IEntitySource PieceNearShapes(WorldEditorAPI api, array<IEntitySource> shapes)
	{
		IEntitySource best;
		float bestDist = START_SEARCH;
		foreach (IEntitySource shapeSrc : shapes)
		{
			ShapeEntity shape = ShapeEntity.Cast(api.SourceToEntity(shapeSrc));
			if (!shape)
				continue;

			array<vector> points = {};
			shape.GetPointsPositions(points);
			if (points.IsEmpty())
				continue;

			vector mat[4];
			shape.GetWorldTransform(mat);
			array<vector> ends = {};
			ends.Insert(ToWorld(points[0], mat));
			ends.Insert(ToWorld(points[points.Count() - 1], mat));
			foreach (vector end : ends)
			{
				m_aFoundPieces.Clear();
				api.GetWorld().QueryEntitiesByAABB(end - Vector(START_SEARCH, 30, START_SEARCH), end + Vector(START_SEARCH, 30, START_SEARCH), OnPieceQuery, null, EQueryEntitiesFlags.ALL);
				foreach (IEntity piece : m_aFoundPieces)
				{
					IEntitySource pieceSrc = api.EntityToSource(piece);
					if (!pieceSrc)
						continue;

					// A piece a build made isn't a start
					string name = pieceSrc.GetName();
					if (name.IndexOf("EoHT_") == 0)
						continue;

					float d = vector.Distance(piece.GetOrigin(), end);
					if (d < bestDist)
					{
						bestDist = d;
						best = pieceSrc;
					}
				}
			}
		}

		return best;
	}

	//------------------------------------------------------------------------------------------------
	//! A spline's curve and points in world space, and what each point asks for (SP_TunnelSplinePointData in its Data)
	protected SP_TunnelSplinePath ReadPath(WorldEditorAPI api, IEntitySource src)
	{
		ShapeEntity shape = ShapeEntity.Cast(api.SourceToEntity(src));
		if (!shape)
			return null;

		SP_TunnelSplinePath path = new SP_TunnelSplinePath();
		path.m_sName = src.GetName();
		if (path.m_sName.IsEmpty())
			path.m_sName = "unnamed " + src.GetClassName();

		path.m_bClosed = shape.IsClosed();
		vector mat[4];
		shape.GetWorldTransform(mat);

		array<vector> anchors = {};
		shape.GetPointsPositions(anchors);
		BaseContainerList points = src.GetObjectArray("Points");
		foreach (int i, vector anchor : anchors)
		{
			SP_TunnelSplineMark mark = new SP_TunnelSplineMark();
			mark.m_iAnchor = i;
			mark.m_vPos = ToWorld(anchor, mat);
			if (points && i < points.Count())
				ReadMark(points.Get(i), mark);

			path.m_aMarks.Insert(mark);
		}

		array<vector> curve = {};
		shape.GenerateTesselatedShape(curve);
		if (curve.Count() < 2)
			curve = anchors;

		foreach (vector local : curve)
		{
			path.m_aCurve.Insert(ToWorld(local, mat));
		}

		return path;
	}

	//------------------------------------------------------------------------------------------------
	protected void ReadMark(BaseContainer point, SP_TunnelSplineMark mark)
	{
		if (!point)
			return;

		BaseContainerList data = point.GetObjectArray("Data");
		if (!data)
			return;

		for (int j = 0; j < data.Count(); j++)
		{
			BaseContainer item = data.Get(j);
			if (!item || item.GetClassName() != "SP_TunnelSplinePointData")
				continue;

			ResourceName piece;
			int kind;
			bool noTurns;
			item.Get("m_sPiece", piece);
			item.Get("m_iKind", kind);
			item.Get("m_bNoTurns", noTurns);
			mark.m_bHasData = true;
			mark.m_sPiece = piece;
			mark.m_iKind = kind;
			mark.m_bNoTurns = noTurns;
			return;
		}
	}

	//------------------------------------------------------------------------------------------------
	//! The selected splines, ready to follow: the one with an end nearest the start piece first (turned to start there),
	//! the others linked to it as branches
	protected bool ReadPaths(WorldEditorAPI api, array<IEntitySource> shapes, vector startPos, notnull array<ref SP_TunnelSplinePath> paths)
	{
		foreach (IEntitySource shapeSrc : shapes)
		{
			SP_TunnelSplinePath read = ReadPath(api, shapeSrc);
			if (read && read.m_aCurve.Count() >= 2)
				paths.Insert(read);
			else
				Print("SP_TunnelGen: a selected spline has fewer than two points, left out", LogLevel.WARNING);
		}

		if (paths.IsEmpty())
		{
			Workbench.Dialog("EoH Tunnel Generator", "The selected spline has fewer than two points.");
			return false;
		}

		int main = 0;
		bool reverse = false;
		float bestDist = 1000000;
		foreach (int p, SP_TunnelSplinePath candidate : paths)
		{
			float dFirst = vector.DistanceXZ(candidate.First(), startPos);
			float dLast = vector.DistanceXZ(candidate.Last(), startPos);
			if (dFirst < bestDist)
			{
				bestDist = dFirst;
				main = p;
				reverse = false;
			}

			if (dLast < bestDist)
			{
				bestDist = dLast;
				main = p;
				reverse = true;
			}
		}

		if (main != 0)
		{
			SP_TunnelSplinePath first = paths[0];
			paths[0] = paths[main];
			paths[main] = first;
		}

		if (reverse)
			paths[0].Reverse();

		foreach (SP_TunnelSplinePath built : paths)
		{
			built.Build(api);
		}

		SP_TunnelSplinePath.Link(paths, api, Math.Max(12, m_fSplineTolerance * 3));
		if (bestDist > 15)
			Print(string.Format("SP_TunnelGen: the spline starts %1 m from the start piece: the first pieces head for it", Math.Round(bestDist)), LogLevel.WARNING);

		foreach (int index, SP_TunnelSplinePath path : paths)
		{
			string role = "main";
			if (path.m_iParent == -2)
				role = "not near any other spline: left out";
			else if (path.m_iParent >= 0)
				role = string.Format("branch off %1 at %2 m", paths[path.m_iParent].m_sName, Math.Round(path.m_fParentS));

			Print(string.Format("SP_TunnelGen: spline %1 '%2': %3 m, %4 points, %5 asking for pieces, %6", index, path.m_sName, Math.Round(path.m_fLength), path.m_aMarks.Count(), path.CountPieces(), role));
			if (path.m_bClosed)
				Print("SP_TunnelGen:   it's closed: followed from its first point round to its last", LogLevel.WARNING);
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	protected bool OnPieceQuery(IEntity entity)
	{
		if (entity.GetPrefabData() && m_Catalog.IndexOfPrefab(entity.GetPrefabData().GetPrefabName()) >= 0)
			m_aFoundPieces.Insert(entity);

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! Tunnel pieces already in the world near the start (not the start itself, not what's about to be replaced)
	//! skip: more entities that aren't obstacles (connect mode's other entrances)
	protected array<ref SP_TunnelObstacle> Obstacles(WorldEditorAPI api, vector start, IEntity startEntity, float reach, array<IEntity> skip = null)
	{
		array<ref SP_TunnelObstacle> obstacles = {};
		if (!m_bAvoidExisting)
			return obstacles;

		m_aFoundPieces.Clear();
		api.GetWorld().QueryEntitiesByAABB(start - Vector(reach, 200, reach), start + Vector(reach, 200, reach), OnPieceQuery, null, EQueryEntitiesFlags.ALL);
		int subScene = api.GetCurrentSubScene();
		foreach (IEntity entity : m_aFoundPieces)
		{
			if (entity == startEntity || (skip && skip.Contains(entity)))
				continue;

			IEntitySource src = api.EntityToSource(entity);
			if (src && IsOfBuild(src, m_iBuiltSeed))
				continue;

			// Its own box, turned with it, a little smaller so pieces that only touch it don't count
			vector low;
			vector high;
			entity.GetBounds(low, high);
			vector mat[4];
			entity.GetWorldTransform(mat);
			SP_TunnelObstacle obstacle = new SP_TunnelObstacle();
			obstacle.m_sName = entity.GetPrefabData().GetPrefabName();
			obstacle.m_vPos = mat[3];
			obstacle.m_fYaw = SP_TunnelGrower.YawOf(mat[2]);
			obstacle.m_vCentre = mat[3] + SP_TunnelGrower.Rot((low + high) * 0.5, obstacle.m_fYaw);
			vector half = (high - low) * 0.5;
			obstacle.m_vHalf = Vector(Math.Max(half[0] - 0.3, 0.05), half[1], Math.Max(half[2] - 0.3, 0.05));
			obstacle.m_fLowY = mat[3][1] + low[1] + 0.3;
			obstacle.m_fHighY = mat[3][1] + high[1] - 0.3;
			obstacles.Insert(obstacle);
		}

		return obstacles;
	}

	//------------------------------------------------------------------------------------------------
	protected void Generate(int seed, int candidates)
	{
		WorldEditorAPI api = Api();
		if (!api || !LoadCatalog(api, false))
			return;

		int startPiece;
		vector startPos;
		float startYaw;
		IEntity startEntity;
		array<IEntitySource> shapes = SelectedShapes(api);
		SP_TunnelGenSettings cfg = Settings();

		// Two or more entrances selected (and no spline): connect them all. The first is the start, the rest are pinned.
		array<ref SP_TunnelPin> pins = {};
		bool connect = false;
		if (shapes.IsEmpty())
			connect = SelectedEntrances(api, pins);

		array<ref SP_TunnelSplinePath> paths = {};
		if (connect)
		{
			SP_TunnelPin first = pins[0];
			pins.RemoveOrdered(0);
			startPiece = first.m_iPiece;
			startPos = first.m_vPos;
			startYaw = first.m_fYaw;
			startEntity = first.m_Entity;
			Print(string.Format("SP_TunnelGen: connect mode: %1 entrances selected; the first, %2, is the start and stays where it is", pins.Count() + 1, first.m_sName));
			SP_TunnelPieceDef connectDef = m_Catalog.m_aPieces[startPiece];
			if (connectDef.m_aSockets.IsEmpty())
			{
				Workbench.Dialog("EoH Tunnel Generator", "The first selected entrance has no socket in the catalog.");
				return;
			}

			vector sockPos = startPos + SP_TunnelGrower.Rot(connectDef.m_aSockets[0].m_vPos, startYaw);
			vector sockDir = SP_TunnelGrower.Rot(connectDef.m_aSockets[0].m_vDir, startYaw);
			SP_TunnelConnect.Check(m_Catalog, cfg, sockDir, connectDef.m_aSockets[0].m_iSize, pins);
			string skipped = "";
			foreach (SP_TunnelPin pin : pins)
			{
				if (pin.m_sSkip.IsEmpty())
				{
					Print(string.Format("SP_TunnelGen:   %1 at %2: socket at %3 facing %4, %5 degrees off the grid", pin.m_sName, pin.m_vPos, pin.m_vSocketPos, pin.m_vSocketDir, Math.Round(pin.m_fGridOff)));
				}
				else
				{
					Print(string.Format("SP_TunnelGen:   %1 left out: %2", pin.m_sName, pin.m_sSkip), LogLevel.WARNING);
					skipped += pin.m_sName + ": " + pin.m_sSkip + "\n";
				}
			}

			if (!SP_TunnelConnect.Plan(api, cfg, sockPos, sockDir, pins, paths))
			{
				Workbench.Dialog("EoH Tunnel Generator", "None of the other selected entrances can be connected:\n\n" + skipped);
				return;
			}
		}
		else
		{
			if (!FindStart(api, shapes, startPiece, startPos, startYaw, startEntity))
				return;

			// Splines selected: the network follows them
			if (!shapes.IsEmpty() && !ReadPaths(api, shapes, startPos, paths))
				return;
		}

		float reach = m_fMaxReach + 30;
		foreach (SP_TunnelSplinePath reachPath : paths)
		{
			foreach (vector point : reachPath.m_aPoints)
			{
				reach = Math.Max(reach, vector.DistanceXZ(point, startPos) + 30);
			}
		}

		// A record selected: that's the build to replace
		IEntityComponentSource selectedRecord = SelectedRecord(api);
		if (selectedRecord)
			selectedRecord.Get("m_iSeed", m_iBuiltSeed);

		if (seed == 0)
		{
			seed = 1000 + Math.AbsInt(System.GetTickCount()) % 900000;
		}

		SP_TunnelPieceDef startDef = m_Catalog.m_aPieces[startPiece];
		Print(string.Format("SP_TunnelGen: growing from %1 at %2, yaw %3; the ground there is at %4", startDef.m_sName, startPos, Math.Round(startYaw), api.GetTerrainSurfaceY(startPos[0], startPos[2])));
		foreach (int si, SP_TunnelSocketDef startSocket : startDef.m_aSockets)
		{
			vector socketAt = startPos + SP_TunnelGrower.Rot(startSocket.m_vPos, startYaw);
			Print(string.Format("SP_TunnelGen:   its socket %1 at %2 facing %3, %4 m under the ground", si, socketAt, SP_TunnelGrower.Rot(startSocket.m_vDir, startYaw), api.GetTerrainSurfaceY(socketAt[0], socketAt[2]) - socketAt[1]));
		}

		// The other entrances are in the world already: not obstacles, not in the way of the world check
		array<IEntity> pinEntities = {};
		foreach (SP_TunnelPin pinned : pins)
		{
			if (pinned.m_Entity)
				pinEntities.Insert(pinned.m_Entity);
		}

		array<ref SP_TunnelObstacle> obstacles = Obstacles(api, startPos, startEntity, reach, pinEntities);
		SP_TunnelGrower grower = new SP_TunnelGrower(m_Catalog, cfg, api, obstacles);
		grower.SetPaths(paths);
		grower.SetPins(pins);
		array<IEntity> ignore = BuildEntities(api, m_iBuiltSeed);
		if (startEntity)
			ignore.Insert(startEntity);

		foreach (IEntity pinEntity : pinEntities)
		{
			ignore.Insert(pinEntity);
		}

		grower.SetWorld(api.GetWorld(), ignore);
		SP_TunnelLayout best;
		int searchStart = System.GetTickCount();
		for (int k = 0; k < candidates; k++)
		{
			int layoutSeed = seed + k * 7919;
			SP_TunnelLayout layout = grower.Grow(layoutSeed, startPiece, startPos, startYaw);
			Print(string.Format("SP_TunnelGen: layout %1 cost %2", layout.Summary(), Math.Round(layout.m_fCost * 10) * 0.1));
			if (!best || layout.m_fCost < best.m_fCost)
				best = layout;
		}

		m_iSeed = best.m_iSeed;
		m_iLastSeed = best.m_iSeed;
		Print(string.Format("SP_TunnelGen: best of %1 in %2 ms: %3 (%4 obstacles in the way, catalog %5)", candidates, System.GetTickCount() - searchStart, best.Summary(), obstacles.Count(), m_Catalog.m_sHash));
		Print("SP_TunnelGen: " + best.Refusals());
		foreach (string why : best.m_aRefused)
		{
			Print("SP_TunnelGen:   refused " + why);
		}

		foreach (string markLine : best.m_aMarkLog)
		{
			Print("SP_TunnelGen:   spline " + markLine);
		}

		foreach (SP_TunnelDocking dock : best.m_aDockings)
		{
			if (dock.m_bDocked)
				Print("SP_TunnelGen: entrance " + dock.Describe());
			else
				Print("SP_TunnelGen: entrance " + dock.Describe(), LogLevel.WARNING);
		}

		foreach (vector hole : best.m_aEntrancePoints)
		{
			Print(string.Format("SP_TunnelGen: new entrance at %1: cut a hole in the terrain there (Terrain Tool, Hole) and shape the ground to it", hole));
		}

		// Nothing grew at all: say why instead of placing a lone dead end
		if (best.m_fLength < 1 && best.m_iRooms == 0)
		{
			string why = "Nothing could be built from the selected piece.\n\n" + best.Refusals();
			if (best.m_iFailCover > 0)
			{
				string kind = "a dead end, corridor or room";
				if (startDef.m_iKind == SP_TunnelKind.ENTRANCE)
					kind = "an entrance";

				why += string.Format("\n\nThe start piece is %1, and the pieces next to it would have too little earth over them. Start from an entrance placed on the ground (TT_Entry_Incline: its pivot on the ground; TT_Entry_Horizontal: its mouth at the foot of a slope), or put a corridor piece at least %2 m under the ground.", kind, m_fMinCover);
			}

			Workbench.Dialog("EoH Tunnel Generator", why);
			return;
		}

		if (m_bDryRun)
		{
			Workbench.Dialog("EoH Tunnel Generator", "Dry run, nothing placed.\n\n" + best.Summary() + "\n\n" + best.DockingText());
			return;
		}

		Place(api, best, cfg, startPiece, startPos, startYaw);
	}

	//================================================================================================
	// Placing
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	//! Every entity a build makes is named after its seed: EoHT_<seed>_<n> (and the record EoHTunnelRecord_<seed>), so a
	//! build can be found again in any layer, in any session
	protected string BuildPrefix(int seed)
	{
		return "EoHT_" + seed + "_";
	}

	//------------------------------------------------------------------------------------------------
	protected bool IsOfBuild(IEntitySource src, int seed)
	{
		if (seed < 0 || !src)
			return false;

		string name = src.GetName();
		return name.IndexOf(BuildPrefix(seed)) == 0 || name == "EoHTunnelRecord_" + seed;
	}

	//------------------------------------------------------------------------------------------------
	protected array<IEntitySource> BuildSources(WorldEditorAPI api, int seed)
	{
		array<IEntitySource> found = {};
		if (seed < 0)
			return found;

		int count = api.GetEditorEntityCount();
		for (int i = 0; i < count; i++)
		{
			IEntitySource src = api.GetEditorEntity(i);
			if (src && !src.GetParent() && IsOfBuild(src, seed))
				found.Insert(src);
		}

		return found;
	}

	//------------------------------------------------------------------------------------------------
	//! A build's entities (the one about to be replaced), so the new plan doesn't steer round it
	protected array<IEntity> BuildEntities(WorldEditorAPI api, int seed)
	{
		array<IEntity> found = {};
		foreach (IEntitySource src : BuildSources(api, seed))
		{
			IEntity entity = api.SourceToEntity(src);
			if (entity)
				found.Insert(entity);
		}

		return found;
	}

	//------------------------------------------------------------------------------------------------
	protected int ClearBuild(WorldEditorAPI api, int seed)
	{
		array<IEntitySource> doomed = BuildSources(api, seed);
		foreach (IEntitySource gone : doomed)
		{
			api.DeleteEntity(gone);
		}

		return doomed.Count();
	}

	//------------------------------------------------------------------------------------------------
	//! Places a prefab with a yaw (as the planner means it: forward +Z turned to sin, cos)
	protected IEntitySource CreatePiece(WorldEditorAPI api, ResourceName prefab, int layerId, vector pos, float yaw, string name = "")
	{
		IEntitySource src = api.CreateEntity(prefab, name, layerId, null, pos, Vector(0, yaw * m_fYawSign, 0));
		if (src && !name.IsEmpty() && src.GetName() != name)
			api.RenameEntity(src, name);

		return src;
	}

	//------------------------------------------------------------------------------------------------
	//! Once a session, in an undo step of its own: which way the editor turns an entity for a yaw. A piece is placed at
	//! 90 degrees, looked at and taken away again.
	protected void YawProbe(WorldEditorAPI api, ResourceName prefab, int layerId, vector at)
	{
		if (m_bYawChecked)
			return;

		m_bYawChecked = true;
		api.BeginEntityAction("EoH tunnels: check rotation");
		IEntitySource src = api.CreateEntity(prefab, "", layerId, null, at, Vector(0, 90, 0));
		IEntity entity;
		if (src)
			entity = api.SourceToEntity(src);

		if (entity)
		{
			vector mat[4];
			entity.GetWorldTransform(mat);
			vector expected = SP_TunnelGrower.Rot("0 0 1", 90);
			if (vector.Dot(mat[2], expected) < 0)
				m_fYawSign = -1;

			Print(string.Format("SP_TunnelGen: rotation check: forward at 90 is %1, expected %2, placing with sign %3", mat[2], expected, m_fYawSign));
		}

		if (src)
			api.DeleteEntity(src);

		api.EndEntityAction();
	}

	//------------------------------------------------------------------------------------------------
	protected void OnBlockerFound(ResourceName resName, string filePath = "")
	{
		m_aFoundBlockers.Insert(resName);
	}

	//------------------------------------------------------------------------------------------------
	protected ResourceName BlockerPrefab()
	{
		if (!m_sBlocker.IsEmpty())
			return m_sBlocker;

		m_aFoundBlockers.Clear();
		Workbench.SearchResources(OnBlockerFound, {"et"}, {"GridPlane_100x100"}, "", true);
		foreach (ResourceName found : m_aFoundBlockers)
		{
			string path = found;
			if (path.Contains("GridPlane_100x100.et"))
			{
				m_sBlocker = found;
				break;
			}
		}

		if (m_sBlocker.IsEmpty())
			Print("SP_TunnelGen: no GridPlane_100x100 prefab found, no light blockers placed", LogLevel.WARNING);

		return m_sBlocker;
	}

	//------------------------------------------------------------------------------------------------
	//! The plane's own size and where its surface is relative to its pivot, measured once at scale 1, in an undo step
	//! of its own (placed far up, looked at, taken away)
	protected bool MeasureBlocker(WorldEditorAPI api, int layerId, vector at)
	{
		if (m_fBlockerSize > 0)
			return true;

		ResourceName prefab = BlockerPrefab();
		if (prefab.IsEmpty())
			return false;

		api.BeginEntityAction("EoH tunnels: measure light blocker");
		IEntitySource src = api.CreateEntity(prefab, "", layerId, null, at, vector.Zero);
		IEntity entity;
		if (src)
			entity = api.SourceToEntity(src);

		if (entity)
		{
			vector low;
			vector high;
			entity.GetWorldBounds(low, high);
			m_vBlockerMid = (low + high) * 0.5 - at;
			m_fBlockerSize = Math.Min(high[0] - low[0], high[2] - low[2]);
			Print(string.Format("SP_TunnelGen: light blocker %1 is %2 by %3 m at scale 1, its middle %4 from its pivot", prefab, high[0] - low[0], high[2] - low[2], m_vBlockerMid));
		}

		if (src)
			api.DeleteEntity(src);

		api.EndEntityAction();
		return m_fBlockerSize > 0.01;
	}

	//------------------------------------------------------------------------------------------------
	//! Planes over a piece, collision off: square tiles as wide as the piece, laid along it (entities only scale evenly,
	//! so one square over a long piece would reach far over its neighbours). Each tile sits just under the lowest ground
	//! over it, and only comes down if that would cut into the top of a tunnel under it.
	protected void PlaceBlockers(WorldEditorAPI api, int layerId, SP_TunnelLayout layout, SP_TunnelPlaced placed, SP_TunnelPieceDef piece, string prefix)
	{
		ResourceName prefab = BlockerPrefab();
		if (prefab.IsEmpty() || m_fBlockerSize <= 0)
			return;

		float margin = Math.Max(m_fBlockerMargin, 0);
		vector low = piece.m_vMin - Vector(margin, 0, margin);
		vector high = piece.m_vMax + Vector(margin, 0, margin);
		float sizeX = high[0] - low[0];
		float sizeZ = high[2] - low[2];
		bool alongZ = sizeZ >= sizeX;
		float tile = Math.Min(sizeX, sizeZ);
		float length = Math.Max(sizeX, sizeZ);
		int tiles = Math.Max(1, Math.Ceil(length / tile - 0.05));
		float step = length / tiles;
		for (int t = 0; t < tiles; t++)
		{
			// The tile's middle, in the piece's space, then the world's
			vector local = (low + high) * 0.5;
			float along = -length * 0.5 + step * (t + 0.5);
			if (alongZ)
				local[2] = local[2] + along;
			else
				local[0] = local[0] + along;

			float size = Math.Max(tile, step);
			vector centre = placed.m_vPos + SP_TunnelGrower.Rot(local, placed.m_fYaw);
			float reach = size * 0.71;

			// The lowest ground over the tile
			float ground = 100000;
			for (int g = 0; g < 9; g++)
			{
				// (Enforce won't take % inside a float sum, so the int parts come first)
				int column = g % 3;
				int row = g / 3;
				float gx = (column - 1) * size * 0.5;
				float gz = (row - 1) * size * 0.5;
				vector over = centre + SP_TunnelGrower.Rot(Vector(gx, 0, gz), placed.m_fYaw);
				ground = Math.Min(ground, api.GetTerrainSurfaceY(over[0], over[2]));
			}

			// The highest tunnel top under it
			float top = -100000;
			foreach (SP_TunnelPlaced other : layout.m_aPlaced)
			{
				if (!other.m_bSolid)
					continue;

				SP_TunnelPieceDef otherPiece = m_Catalog.m_aPieces[other.m_iPiece];
				if (otherPiece.m_iKind == SP_TunnelKind.ENTRANCE)
					continue;

				float otherReach = Math.Sqrt(other.m_vHalf[0] * other.m_vHalf[0] + other.m_vHalf[2] * other.m_vHalf[2]);
				if (vector.DistanceXZ(other.m_vCentre, centre) > reach + otherReach)
					continue;

				top = Math.Max(top, other.m_vPos[1] + otherPiece.m_vMax[1]);
			}

			float height = ground - m_fBlockerDepth;
			if (height < top + 0.2)
			{
				m_iBlockersHigh++;
				height = top + 0.2;
			}

			float scale = size / m_fBlockerSize;
			vector pivot = centre - SP_TunnelGrower.Rot(m_vBlockerMid * scale, placed.m_fYaw);
			pivot[1] = height - m_vBlockerMid[1] * scale;
			IEntitySource src = CreatePiece(api, prefab, layerId, pivot, placed.m_fYaw, prefix + "_" + t);
			if (!src)
				continue;

			api.SetVariableValue(src, null, "scale", scale.ToString());
			for (int c = 0; c < src.GetComponentCount(); c++)
			{
				IEntityComponentSource component = src.GetComponent(c);
				if (!component)
					continue;

				string className = component.GetClassName();
				if (className.Contains("RigidBody"))
				{
					array<ref ContainerIdPathEntry> path = {new ContainerIdPathEntry("components", c)};
					api.SetVariableValue(src, path, "Enabled", "0");
				}
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	// EoH Tunnel Network's dark probes: their boxes are 4.6 x 4.4 x 8 (corridor), 9.6 x 4.2 x 9.6 (junction),
	// 13.6 x 5.4 x 13.6 (small room), 19 x 5.4 x 19 (room)
	protected static const ResourceName PROBE_CORRIDOR = "{352949EEDBDE3131}Prefabs/Tunnels/TT/TT_TunnelProbe.et";
	protected static const ResourceName PROBE_HUB = "{DCB788BCD0E04851}Prefabs/Tunnels/TT/TT_TunnelProbe_Hub.et";
	protected static const ResourceName PROBE_ROOM_SMALL = "{FD5CC9ADB86752B5}Prefabs/Tunnels/TT/TT_TunnelProbe_RoomSmall.et";
	protected static const ResourceName PROBE_ROOM = "{B27654EF25D5E71D}Prefabs/Tunnels/TT/TT_TunnelProbe_Room.et";
	protected int m_iProbes;

	//------------------------------------------------------------------------------------------------
	protected void Probe(WorldEditorAPI api, int layerId, ResourceName prefab, vector at, float yaw, string name)
	{
		if (CreatePiece(api, prefab, layerId, at, yaw, name))
			m_iProbes++;
	}

	//------------------------------------------------------------------------------------------------
	//! Dark probes over a piece. A room: the smallest probe that covers it, or room probes laid over a bigger one. A
	//! straight run up to 8.5 m: one along it. Anything else (turns, slopes, U-turns, the ladder): one along each of its
	//! openings, a little way in, and one in the middle of its box.
	protected void PlaceProbes(WorldEditorAPI api, int layerId, SP_TunnelPlaced placed, SP_TunnelPieceDef piece, string prefix)
	{
		vector mid = (piece.m_vMin + piece.m_vMax) * 0.5;
		vector size = piece.m_vMax - piece.m_vMin;
		vector centre = placed.m_vPos + SP_TunnelGrower.Rot(mid, placed.m_fYaw);
		if (piece.m_iKind == SP_TunnelKind.ROOM)
		{
			float wide = Math.Max(size[0], size[2]) + 0.6;
			ResourceName roomProbe = PROBE_ROOM;
			float covers = 19;
			if (wide <= 9.6)
			{
				roomProbe = PROBE_HUB;
				covers = 9.6;
			}
			else if (wide <= 13.6)
			{
				roomProbe = PROBE_ROOM_SMALL;
				covers = 13.6;
			}

			int acrossX = Math.Max(1, Math.Ceil((size[0] + 0.6) / covers));
			int acrossZ = Math.Max(1, Math.Ceil((size[2] + 0.6) / covers));
			int n = 0;
			for (int ix = 0; ix < acrossX; ix++)
			{
				for (int iz = 0; iz < acrossZ; iz++)
				{
					vector local = mid;
					local[0] = piece.m_vMin[0] + size[0] * (ix + 0.5) / acrossX;
					local[2] = piece.m_vMin[2] + size[2] * (iz + 0.5) / acrossZ;
					Probe(api, layerId, roomProbe, placed.m_vPos + SP_TunnelGrower.Rot(local, placed.m_fYaw), placed.m_fYaw, prefix + "_" + n);
					n++;
				}
			}

			return;
		}

		// A straight run (two openings facing apart, at one height): one probe along it
		if (piece.m_aSockets.Count() == 2)
		{
			SP_TunnelSocketDef a = piece.m_aSockets[0];
			SP_TunnelSocketDef b = piece.m_aSockets[1];
			// ...and really in line: a dogleg's exit faces the same way but sits 4.6 m to the side, so its mouths lie outside one
			// probe along the middle (their wall strips then got the sky's light)
			vector ab = b.m_vPos - a.m_vPos;
			vector sideways = ab - a.m_vDir * vector.Dot(ab, a.m_vDir);
			if (vector.Dot(a.m_vDir, b.m_vDir) < -0.99 && Math.AbsFloat(a.m_vPos[1] - b.m_vPos[1]) < 0.3 && vector.Distance(a.m_vPos, b.m_vPos) < 8.5 && sideways.Length() < 0.4)
			{
				Probe(api, layerId, PROBE_CORRIDOR, centre, placed.m_fYaw + SP_TunnelGrower.YawOf(b.m_vDir), prefix + "_0");
				return;
			}
		}

		int k = 0;
		foreach (SP_TunnelSocketDef socket : piece.m_aSockets)
		{
			if (socket.m_iRole != SP_TunnelRole.PATH)
				continue;

			vector inside = socket.m_vPos - socket.m_vDir * 3.5;
			inside[1] = socket.m_vPos[1] + 0.3;
			Probe(api, layerId, PROBE_CORRIDOR, placed.m_vPos + SP_TunnelGrower.Rot(inside, placed.m_fYaw), placed.m_fYaw + SP_TunnelGrower.YawOf(socket.m_vDir), prefix + "_" + k);
			k++;
		}

		Probe(api, layerId, PROBE_CORRIDOR, centre, placed.m_fYaw, prefix + "_" + k);
	}

	//------------------------------------------------------------------------------------------------
	//! In separate undo steps, each logged first, so if the editor ever objects it's clear to what: the last build
	//! cleared, the pieces, the light blockers, the record
	protected void Place(WorldEditorAPI api, SP_TunnelLayout layout, SP_TunnelGenSettings cfg, int startPiece, vector startPos, float startYaw)
	{
		int subScene = api.GetCurrentSubScene();

		// The last build goes
		if (m_iBuiltSeed >= 0)
		{
			Print(string.Format("SP_TunnelGen: step 1, clearing build %1", m_iBuiltSeed));
			api.BeginEntityAction("EoH tunnels: clear last build");
			int removed = ClearBuild(api, m_iBuiltSeed);
			api.EndEntityAction();
			Print(string.Format("SP_TunnelGen: cleared %1 entities", removed));
		}

		// Into the active layer
		int layerId = -1;
		string layer = api.GetActiveSubsceneLayer(subScene);
		if (!layer.IsEmpty())
			layerId = api.GetSubsceneLayerId(subScene, layer);

		if (layerId < 0)
		{
			layerId = api.GetCurrentEntityLayerId();
			layer = api.GetSubsceneLayerPath(subScene, layerId);
		}

		m_iBuiltSeed = layout.m_iSeed;
		string prefix = BuildPrefix(layout.m_iSeed);
		YawProbe(api, m_Catalog.m_aPieces[startPiece].m_sPrefab, layerId, startPos + "0 50 0");

		Print(string.Format("SP_TunnelGen: step 2, placing %1 pieces into %2", layout.m_aPlaced.Count() - 1, layer));
		api.BeginEntityAction("EoH tunnels: generate " + layout.m_iSeed);
		int made = 0;
		foreach (int i, SP_TunnelPlaced placed : layout.m_aPlaced)
		{
			// The start piece is already in the world, and so are the pinned entrances (docked ones are moved below)
			if (i == 0 || placed.m_iPin >= 0)
				continue;

			SP_TunnelPieceDef piece = m_Catalog.m_aPieces[placed.m_iPiece];
			if (CreatePiece(api, piece.m_sPrefab, layerId, placed.m_vPos, placed.m_fYaw, prefix + i))
				made++;
		}

		api.EndEntityAction();
		Print(string.Format("SP_TunnelGen: placed %1 pieces", made));

		// Connect mode: each docked entrance to the pose that meets the tunnel, one undo step each
		if (layout.m_iPinned > 0)
		{
			Print(string.Format("SP_TunnelGen: step 2b, docking %1 of %2 entrances", layout.m_iDocked, layout.m_iPinned));
			foreach (SP_TunnelDocking dock : layout.m_aDockings)
			{
				if (dock.m_bDocked)
					MoveEntrance(api, dock);
			}
		}

		bool packOnly = m_eKit == SP_TunnelCatalog.KIT_EOH;
		if (m_bLightBlockers && packOnly)
		{
			Print("SP_TunnelGen: step 3, light blockers");
			m_iBlockersHigh = 0;
			MeasureBlocker(api, layerId, startPos + "0 60 0");
			api.BeginEntityAction("EoH tunnels: light blockers " + layout.m_iSeed);
			foreach (int bi, SP_TunnelPlaced blocked : layout.m_aPlaced)
			{
				SP_TunnelPieceDef blockedPiece = m_Catalog.m_aPieces[blocked.m_iPiece];
				if (bi > 0 && blocked.m_bSolid && blockedPiece.m_iKind != SP_TunnelKind.ENTRANCE)
					PlaceBlockers(api, layerId, layout, blocked, blockedPiece, prefix + "LB" + bi);
			}

			api.EndEntityAction();
			if (m_iBlockersHigh > 0)
				Print(string.Format("SP_TunnelGen: %1 light blocker tiles had to go lower than asked (the ground over the tunnel is thin there), just over the tunnel roof", m_iBlockersHigh), LogLevel.WARNING);
		}

		// Dark probes for both kits: characters, weapons and anything that isn't the tunnel take the sky's light, and
		// in the dark the picture is brightened to match, so without them the player's own hands glow
		if (m_bDarkProbes)
		{
			Print("SP_TunnelGen: step 3b, dark probes");
			m_iProbes = 0;
			api.BeginEntityAction("EoH tunnels: dark probes " + layout.m_iSeed);
			foreach (int pi, SP_TunnelPlaced probed : layout.m_aPlaced)
			{
				SP_TunnelPieceDef probedPiece = m_Catalog.m_aPieces[probed.m_iPiece];
				int kind = probedPiece.m_iKind;
				if (kind == SP_TunnelKind.MASK || kind == SP_TunnelKind.ENTRANCE || kind == SP_TunnelKind.DOORWAY || kind == SP_TunnelKind.DOORCAP)
					continue;

				// The start piece too, unless it's an entrance (those fade from daylight on their own)
				PlaceProbes(api, layerId, probed, probedPiece, prefix + "DP" + pi);
			}

			api.EndEntityAction();
			Print(string.Format("SP_TunnelGen: %1 dark probes", m_iProbes));
		}

		if (m_bSaveRecord)
		{
			Print("SP_TunnelGen: step 4, record");
			api.BeginEntityAction("EoH tunnels: record " + layout.m_iSeed);
			PlaceRecord(api, layerId, layout, cfg, startPiece, startPos, startYaw);
			api.EndEntityAction();
		}

		Print(string.Format("SP_TunnelGen: built %1 pieces into layer %2", made, layer));
		string dockText = "";
		if (layout.m_iPinned > 0)
			dockText = "\n\n" + layout.DockingText();

		Workbench.Dialog("EoH Tunnel Generator", string.Format("Built into layer %1, its entities named %4*.\n\n%2\n\n%3%5\n\nNew entrances need a hole cut in the terrain: see the log for where.", layer, layout.Summary(), layout.Refusals(), prefix, dockText));
	}

	//------------------------------------------------------------------------------------------------
	protected void PlaceRecord(WorldEditorAPI api, int layerId, SP_TunnelLayout layout, SP_TunnelGenSettings cfg, int startPiece, vector startPos, float startYaw)
	{
		IEntitySource src = api.CreateEntity("GenericEntity", "EoHTunnelRecord_" + layout.m_iSeed, layerId, null, startPos + "0 2 0", vector.Zero);
		if (!src)
		{
			Print("SP_TunnelGen: couldn't create the record entity", LogLevel.WARNING);
			return;
		}

		api.RenameEntity(src, "EoHTunnelRecord_" + layout.m_iSeed);

		api.CreateComponent(src, "SP_TunnelGenRecordComponent");
		int index = -1;
		for (int c = 0; c < src.GetComponentCount(); c++)
		{
			if (src.GetComponent(c).GetClassName() == "SP_TunnelGenRecordComponent")
				index = c;
		}

		if (index < 0)
		{
			Print("SP_TunnelGen: couldn't add the record component", LogLevel.WARNING);
			return;
		}

		array<ref ContainerIdPathEntry> path = {new ContainerIdPathEntry("components", index)};
		api.SetVariableValue(src, path, "m_iSeed", layout.m_iSeed.ToString());
		api.SetVariableValue(src, path, "m_sSettings", cfg.Write());
		api.SetVariableValue(src, path, "m_sCatalogHash", m_Catalog.m_sHash);
		api.SetVariableValue(src, path, "m_vStartPos", string.Format("%1 %2 %3", startPos[0], startPos[1], startPos[2]));
		api.SetVariableValue(src, path, "m_fStartYaw", startYaw.ToString());
		api.SetVariableValue(src, path, "m_sStartPrefab", m_Catalog.m_aPieces[startPiece].m_sPrefab);
		api.SetVariableValue(src, path, "m_sSummary", layout.Summary());
	}

	//================================================================================================
	// Verifying the catalog
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	//! Every piece in a row, high over the middle of the map (or over the selection), with a short straight on each of its
	//! corridor sockets and a standing doorway on each doorframe, so a wrong socket shows at a glance
	protected void Verify(WorldEditorAPI api)
	{
		vector origin = "2048 0 2048";
		if (api.GetSelectedEntitiesCount() > 0)
		{
			IEntity selected = api.SourceToEntity(api.GetSelectedEntity(0));
			if (selected)
				origin = selected.GetOrigin();
		}

		origin[1] = api.GetTerrainSurfaceY(origin[0], origin[2]) + 40;
		int subScene = api.GetCurrentSubScene();
		api.BeginEntityAction("EoH tunnels: verify catalog");
		string layer = api.CreateSubsceneLayer(subScene, "EoHTunnels_Verify");
		int layerId = api.GetSubsceneLayerId(subScene, layer);
		if (layerId < 0)
			layerId = api.GetCurrentEntityLayerId();

		array<int> straights = {-1, -1, -1};
		int doorway = -1;
		foreach (int index, SP_TunnelPieceDef piece : m_Catalog.m_aPieces)
		{
			if (piece.m_iKind == SP_TunnelKind.STRAIGHT && piece.m_sName.Contains("3.5"))
				straights[piece.m_iSize] = index;

			if (piece.m_iKind == SP_TunnelKind.DOORWAY && piece.m_iSize == SP_TunnelSize.S)
				doorway = index;
		}

		float x = 0;
		foreach (SP_TunnelPieceDef shown : m_Catalog.m_aPieces)
		{
			if (shown.m_iKind == SP_TunnelKind.MASK)
				continue;

			vector size = shown.m_vMax - shown.m_vMin;
			vector at = origin + Vector(x - shown.m_vMin[0] + 6, 0, 0);
			x += size[0] + 20;
			CreatePiece(api, shown.m_sPrefab, layerId, at, 0);
			Print(string.Format("SP_TunnelGen verify: %1 (%2, %3) at %4, %5 sockets", shown.m_sName, SP_TunnelKind.Name(shown.m_iKind), SP_TunnelSize.Name(shown.m_iSize), at, shown.m_aSockets.Count()));
			foreach (int s, SP_TunnelSocketDef socket : shown.m_aSockets)
			{
				vector openPos = at + socket.m_vPos;
				Print(string.Format("SP_TunnelGen verify:   socket %1 '%2' at %3 facing %4, %5 %6", s, socket.m_sBone, socket.m_vPos, socket.m_vDir, SP_TunnelSize.Name(socket.m_iSize), socket.m_iRole));
				int attach = -1;
				if (socket.m_iRole == SP_TunnelRole.PATH && socket.m_iSize <= SP_TunnelSize.P)
					attach = straights[socket.m_iSize];
				else if (socket.m_iRole == SP_TunnelRole.DOOR)
					attach = doorway;

				if (attach < 0)
					continue;

				SP_TunnelPieceDef other = m_Catalog.m_aPieces[attach];
				foreach (SP_TunnelSocketDef otherSocket : other.m_aSockets)
				{
					bool matches = (socket.m_iRole == SP_TunnelRole.PATH && otherSocket.m_iRole == SP_TunnelRole.PATH) || (socket.m_iRole == SP_TunnelRole.DOOR && otherSocket.m_iRole == SP_TunnelRole.ROOMSIDE);
					if (!matches)
						continue;

					vector pos;
					float yaw;
					SP_TunnelGrower.Attach(openPos, socket.m_vDir, otherSocket, pos, yaw);
					CreatePiece(api, other.m_sPrefab, layerId, pos, yaw);
					break;
				}
			}
		}

		api.EndEntityAction();
		Workbench.Dialog("EoH Tunnel Generator", "Every piece is laid out in layer " + layer + ", 40 m up, with a straight (or doorway) on each socket. Anything that doesn't line up is a wrong socket. Delete the layer's entities when done.");
	}
}
#endif
