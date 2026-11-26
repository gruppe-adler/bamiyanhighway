//! On every piece of the tunnel test kit (TT_). While the camera is inside one, the camera's exposure is held at one
//! level instead of the game's own: left to itself the game brightens the picture in the dark until anything with a
//! little light on it (the player's own body) glows, and brightens it by a different amount in every corner of the
//! tunnels. In an entrance it comes in by how deep under the ground the camera is. Out in the open again, the game's
//! exposure takes over. Modelled on the EoH tunnel network's EOH_ProcSight hold.
[ComponentEditorProps(category: "EoH/Tunnels", description: "Holds the camera's exposure while it is inside this tunnel piece")]
class SP_TunnelExposureComponentClass : ScriptComponentClass
{
}

class SP_TunnelExposureComponent : ScriptComponent
{
	[Attribute("0", UIWidgets.CheckBox, "An entrance: the picture darkens by how deep under the ground the camera is, not all at once")]
	protected bool m_bEntrance;

	[Attribute("0.005", UIWidgets.EditBox, "How bright the picture is held in the tunnels (the camera's exposure gain), the same by day and by night. Lower is darker; 0.08 was too dark for the unlit kit")]
	protected float m_fTunnelGain;

	[Attribute("0", UIWidgets.CheckBox, "Tells the engine this piece is a dominant object that is not culled the standard way (EntityFlags.FEATURE), to try to stop tunnel pieces vanishing past about 20 m underground. Draws nothing; may cost frame time. Off unless you are testing")]
	protected bool m_bKeepRendered;

	[Attribute("0", UIWidgets.CheckBox, "Take part in the exposure control (held exposure, colour grade, per-soldier probe, flashlight boost). Off: only the no-cull flag, and the engine's own exposure with the piece's probe, as vanilla interiors do")]
	protected bool m_bExposureControl;

	// Play mode: once a second the engine is asked whether every piece still has the no-cull flag (in the editor, where it stays
	// as set at spawn, nothing gets culled; in play something did)
	protected static ref array<SP_TunnelExposureComponent> s_aKeep;
	// TEST: overrides every prefab's m_bKeepRendered in play mode: no piece gets the flag, to see whether flagging all of them is
	// what makes pieces vanish / turn white. The editor keeps it. false: as the prefabs say
	static const bool PLAY_WITHOUT_FLAG = false;
	protected static ArmaReforgerScripted s_KeepGame;		// the game whose call queue runs the check
	protected static int s_iKeepReported = -1;				// pieces counted when the count was last logged
	protected static int s_iFlagReported = -1;				// and how many of them had the flag
	protected static int s_iCountLogged;
	protected static const int COUNT_LOG_MS = 10000;		// the count is logged when it changes, and this often anyway
	protected static string s_sLookedAt;

	// How many pieces get the flag (diag menu Win+Alt > Tunnels cull > Max flagged pieces). At the top of the range: every piece,
	// set once at spawn, nothing taken away. Lower: only the nearest ones connected to the camera's piece, along the openings
	static const int CAP_ALL = 300;
	static const float KEEP_PATH = 200;			// only up to this far along the tunnels, metres
	static const float KEEP_OUTSIDE = 100;		// camera in no piece (on the surface): start from the pieces this near
	static const float KEEP_JOINT = 1.5;		// openings this close are joined (an entry tilted 10 degrees is 0.8 m off)
	static const int CAP_DEFAULT = 300;			// = CAP_ALL: every piece flagged (the user's choice); lower it in the diag menu to try a limit
	protected static int s_iKeepCap = CAP_DEFAULT;
	// who gets them: what the player can see
	static const int SEEN_FOR_MS = 3000;		// a piece a ray has hit stays preferred this long
	static const float SIGHT_RANGE = 150;
	static const float OPENING_RANGE = 90;		// doorways this near and in front get a ray through them
	protected int m_iSeenAt = -100000;
	static const int FOV_DEFAULT = 60;			// degrees either side of the view's middle that count as in view (diag slider)
	protected static int s_iViewHalf = FOV_DEFAULT;
	static const float OUT_OF_VIEW = 3;			// a piece out of view counts as this many times further along the tunnels,
	static const float OUT_OF_VIEW_ADD = 20;	// plus this
	static const float SEEN_FACTOR = 0.5;		// and one a ray has hit as this much nearer
	protected static int s_iSliderWarned;
	protected static int s_iSightPhase;
	protected static int s_iChoiceLogged;
	protected static bool s_bKeepRelink;		// show / hide the piece after changing its flag, in case the engine only reads it then
	protected static bool s_bLinksDirty = true;
	protected static int s_iJoins;
	protected static int s_iNoOpenings;
	protected static int s_iKeepRun;			// numbers each update: marks what it has seen
	protected bool m_bKept = true;				// should have the flag
	protected ref array<vector> m_aOpenings = {};					// world
	protected ref array<SP_TunnelExposureComponent> m_aLinks = {};	// the pieces joined to this one
	protected vector m_vWorldMins;
	protected vector m_vWorldMaxs;
	protected float m_fPath;				// along the tunnels from the camera, this update
	protected int m_iSeen;
	protected int m_iDone;
	// Test switches (diag menu Win+Alt > Tunnels cull): poke the pieces near the camera, in case a static piece that nothing
	// ever updates is what gets dropped
	protected static const float FORCE_WITHIN = 120;
	protected static bool s_bForceDiag;
	protected static bool s_bForceUpdate;		// Update() and the flag again, every frame
	protected static bool s_bForceShow;			// also hidden and shown again, every frame
	protected static bool s_bForceMesh;			// the model assigned again, once a second
	protected static bool s_bForceLod;			// fixed at the full detail level
	protected static bool s_bLodFixed;
	// Test switches for the flags that decide how the entity sits in the engine's scene tree (same diag menu)
	protected static bool s_bFlagNoStatic;
	protected static bool s_bFlagActive;
	protected static bool s_bFlagNoTree;
	protected static bool s_bFlagRelink;
	protected static bool s_bProbesOff;			// test: the pieces' dark probes switched off
	protected static ref array<EnvironmentProbeEntity> s_aProbesFound;
	protected static int s_iProbesSeen;			// every probe the query met, ours or not
	protected int m_iStartFlags;			// as the piece spawned, to put back
	// the sight check: does the engine draw what is in view?
	protected static int s_iSightRays;
	protected static int s_iSightMissed;
	protected static int s_iSightReported;
	protected static int s_iMissLogged;
	protected static bool s_bStartLogged;

	protected static ref array<SP_TunnelExposureComponent> s_aPieces;
	protected vector m_vOrigin;
	protected vector m_vMins;
	protected vector m_vMaxs;
	protected static SP_TunnelExposureComponent s_LastPiece;     // the piece the camera was in last: checked first
	protected static float s_fDark;
	protected static int s_iNextScan;
	protected static bool s_bFeatureOff;
	protected static float s_fDiagGain;          // diag values, read ten times a second (not every frame)
	protected static bool s_bDiagNoGrade;
	protected static bool s_bDiagLog;
	protected static bool s_bDiagHoldOff;
	protected static bool s_bDiagTorchOff;
	protected static float s_fSentGain = -1;

	// A small, completely black probe carried by every soldier underground (EoH's fix for the "blue ghost"): the walls
	// take no sky light by material, characters can't, and whatever reaches them the held exposure would blow up
	protected static const ResourceName MAN_PROBE = "{BB22F0555C450BAA}Prefabs/Tunnels/TT/TT_ManProbe.et";
	protected static ref array<IEntity> s_aProbeMen;
	protected static ref array<IEntity> s_aManProbes;
	protected static ref Resource s_ManProbeRes;
	protected static int s_iNextManTick;

	// The player's flashlight underground: at a dark picture the game's torch alone is too weak, so while it is on a soft
	// spill round the holder and a beam along the view are added (EoH's torch lights, EOH_ProcData.UpdateSpill)
	protected static const float SPILL_LV = 5;
	protected static const float BEAM_LV = 6.5;
	protected static const float BEAM_CONE = 35;
	protected static LightEntity s_Spill;
	protected static LightEntity s_Beam;
	protected static bool s_bTorchOn;
	protected static int s_iNextTorchCheck;
	protected static float s_fGain = 0.005;
	protected static float s_fOutsideGain = 0.02;	// what the game's exposure made of the open air, last seen
	protected static float s_fHeldStops;
	protected static int s_iHeldCamera = -1;
	protected static int s_iLastFrame;
	protected static int s_iOutSince;
	protected static int s_iLastLog;

	//------------------------------------------------------------------------------------------------
	override void OnPostInit(IEntity owner)
	{
		// The cull flag works in the editor view too (the exposure hold below does not)
		if (m_bKeepRendered)
		{
			ArmaReforgerScripted running = GetGame();
			if (!PLAY_WITHOUT_FLAG || !running || !running.InPlayMode())
				owner.SetFlags(EntityFlags.FEATURE, false);

			WatchFlag();
		}

		ArmaReforgerScripted game = GetGame();
		if (!game || !game.InPlayMode() || System.IsConsoleApp() || !m_bExposureControl)
			return;

		if (!s_aPieces)
		{
			s_aPieces = {};
			s_iLastFrame = System.GetTickCount();
			game.GetCallqueue().CallLater(Expose, 0, true);
		}

		s_aPieces.Insert(this);
		m_vOrigin = owner.GetOrigin();
		owner.GetBounds(m_vMins, m_vMaxs);
		s_fGain = Math.Clamp(m_fTunnelGain, 0.0005, 2);
		RegisterDiag();
	}

	//------------------------------------------------------------------------------------------------
	protected void WatchFlag()
	{
		ArmaReforgerScripted game = GetGame();
		if (!game || !game.InPlayMode() || System.IsConsoleApp())
			return;

		if (!s_aKeep)
			s_aKeep = {};

		s_aKeep.Insert(this);
		s_bLinksDirty = true;
		IEntity me = GetOwner();
		if (me)
		{
			m_iStartFlags = me.GetFlags();
			me.SetFlags(EntityFlags.SET_RENDERED, false);		// makes IsRendered() work
			if (!s_bStartLogged)
			{
				s_bStartLogged = true;
				int raw = m_iStartFlags;
				Print(string.Format("SP_TunnelKeep: raw flags of a piece %1; values VISIBLE %2, TRACEABLE %3, FEATURE %4, STATIC %5, ACTIVE %6, NO_TREE %7, STREAMABLE %8, PROXY %9", raw, EntityFlags.VISIBLE, EntityFlags.TRACEABLE, EntityFlags.FEATURE, EntityFlags.STATIC, EntityFlags.ACTIVE, EntityFlags.NO_TREE, EntityFlags.STREAMABLE, EntityFlags.PROXY));
				Print(string.Format("SP_TunnelKeep: more values NO_LINK %1, SET_RENDERED %2, USER1 %3, USER5 %4, RELATIVE_Y %5, EDITOR_ONLY %6, DISABLED %7, UPDATE_LINK %8", EntityFlags.NO_LINK, EntityFlags.SET_RENDERED, EntityFlags.USER1, EntityFlags.USER5, EntityFlags.RELATIVE_Y, EntityFlags.EDITOR_ONLY, EntityFlags.DISABLED, EntityFlags.UPDATE_LINK));
				Print(string.Format("SP_TunnelKeep: a piece's flags at spawn: visible %1, static %2, active %3, no tree %4, streamable %5, feature %6", (m_iStartFlags & EntityFlags.VISIBLE) != 0, (m_iStartFlags & EntityFlags.STATIC) != 0, (m_iStartFlags & EntityFlags.ACTIVE) != 0, (m_iStartFlags & EntityFlags.NO_TREE) != 0, (m_iStartFlags & EntityFlags.STREAMABLE) != 0, (m_iStartFlags & EntityFlags.FEATURE) != 0));
			}
		}

		if (game == s_KeepGame)
			return;

		s_KeepGame = game;
		s_iKeepReported = -1;
		game.GetCallqueue().CallLater(CheckFlags, 1000, true);
		game.GetCallqueue().CallLater(ForceTick, 0, true);
		game.GetCallqueue().CallLater(KeepTick, 100, true);
		RegisterForceDiag();
	}

	//------------------------------------------------------------------------------------------------
	protected static void RegisterForceDiag()
	{
		if (s_bForceDiag)
			return;

		s_bForceDiag = true;
		DiagMenu.RegisterMenu(SCR_DebugMenuID.SP_TUNNELS_CULL_MENU, "Tunnels cull", "");
		DiagMenu.RegisterRange(SCR_DebugMenuID.SP_TUNNELS_KEEP_CAP, "", "Max flagged pieces", "Tunnels cull", string.Format("0, %1, %2, 4", CAP_ALL, CAP_DEFAULT));
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_KEEP_RELINK, "", "Re-show piece after flag change", "Tunnels cull");
		DiagMenu.RegisterRange(SCR_DebugMenuID.SP_TUNNELS_KEEP_FOV, "", "In view: degrees either side", "Tunnels cull", string.Format("20, 180, %1, 5", FOV_DEFAULT));
		DiagMenu.SetRangeValue(SCR_DebugMenuID.SP_TUNNELS_KEEP_CAP, CAP_DEFAULT);
		DiagMenu.SetRangeValue(SCR_DebugMenuID.SP_TUNNELS_KEEP_FOV, FOV_DEFAULT);
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_UPDATE, "", "Update every frame", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_SHOW, "", "Hide and show every frame", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_MESH, "", "Assign model again (1/s)", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_LOD, "", "Force full detail (LOD 0)", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_NOSTATIC, "", "Flags: remove STATIC", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_ACTIVE, "", "Flags: add ACTIVE", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_NOTREE, "", "Flags: add NO_TREE", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_RELINK, "", "Flags: relink every second", "Tunnels cull");
		DiagMenu.RegisterBool(SCR_DebugMenuID.SP_TUNNELS_PROBES_OFF, "", "Dark probes off", "Tunnels cull");
	}

	//------------------------------------------------------------------------------------------------
	//! Once a second: what is switched on
	protected static void ReadForceDiag()
	{
		if (!s_bForceDiag)
			return;

		bool update = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_UPDATE);
		bool show = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_SHOW);
		bool mesh = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_MESH);
		bool lod = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FORCE_LOD);
		if (update == s_bForceUpdate && show == s_bForceShow && mesh == s_bForceMesh && lod == s_bForceLod)
			return;

		s_bForceUpdate = update;
		s_bForceShow = show;
		s_bForceMesh = mesh;
		s_bForceLod = lod;
		Print(string.Format("SP_TunnelKeep: forcing: update %1, hide and show %2, model again %3, full detail %4", update, show, mesh, lod));
	}

	//------------------------------------------------------------------------------------------------
	protected static bool NearCamera(IEntity entity, BaseWorld world, vector eye)
	{
		return entity && entity.GetWorld() == world && vector.DistanceSq(entity.GetOrigin(), eye) <= FORCE_WITHIN * FORCE_WITHIN;
	}

	//------------------------------------------------------------------------------------------------
	//! Every frame, but does nothing unless a switch is on
	protected static void ForceTick()
	{
		if (!s_aKeep || (!s_bForceUpdate && !s_bForceShow))
			return;

		ArmaReforgerScripted game = GetGame();
		if (!game || !game.GetWorld())
			return;

		BaseWorld world = game.GetWorld();
		vector view[4];
		world.GetCurrentCamera(view);
		foreach (SP_TunnelExposureComponent piece : s_aKeep)
		{
			if (!piece || !NearCamera(piece.GetOwner(), world, view[3]))
				continue;

			IEntity owner = piece.GetOwner();
			if (s_bForceShow)
			{
				owner.ClearFlags(EntityFlags.VISIBLE, false);
				owner.SetFlags(EntityFlags.VISIBLE, false);
			}

			if (piece.m_bKept)
				owner.SetFlags(EntityFlags.FEATURE, false);

			owner.Update();
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Once a second: the slower pokes
	protected static void ForceSlow(BaseWorld world)
	{
		ReadForceDiag();
		bool unfix = s_bLodFixed && !s_bForceLod;
		if (!s_bForceMesh && !s_bForceLod && !unfix)
			return;

		vector view[4];
		world.GetCurrentCamera(view);
		foreach (SP_TunnelExposureComponent piece : s_aKeep)
		{
			if (!piece || !NearCamera(piece.GetOwner(), world, view[3]))
				continue;

			IEntity owner = piece.GetOwner();
			if (s_bForceMesh && owner.GetVObject())
			{
				owner.SetObject(owner.GetVObject(), "");
				if (piece.m_bKept)
					owner.SetFlags(EntityFlags.FEATURE, false);
				owner.Update();
			}

			if (s_bForceLod)
				owner.SetFixedLOD(0);
			else if (unfix)
				owner.SetFixedLOD(-1);
		}

		s_bLodFixed = s_bForceLod;
	}

	//------------------------------------------------------------------------------------------------
	protected void SetKept(bool keep)
	{
		IEntity owner = GetOwner();
		if (!owner)
			return;

		m_bKept = keep;
		if (keep)
			owner.SetFlags(EntityFlags.FEATURE, false);
		else
			owner.ClearFlags(EntityFlags.FEATURE, false);

		owner.Update();
		if (!s_bKeepRelink)
			return;

		owner.ClearFlags(EntityFlags.VISIBLE, false);
		owner.Update();
		owner.SetFlags(EntityFlags.VISIBLE, false);
		owner.Update();
	}

	//------------------------------------------------------------------------------------------------
	//! A diag slider's value; one outside its range (the menu has handed out -248 for a 0..300 slider) is put back to the default
	protected static int SliderValue(int id, int low, int high, int fallback)
	{
		int value = Math.Round(DiagMenu.GetRangeValue(id));
		if (value >= low && value <= high)
			return value;

		int now = System.GetTickCount();
		if (now - s_iSliderWarned > 10000)		// this runs ten times a second
		{
			s_iSliderWarned = now;
			Print(string.Format("SP_TunnelKeep: a slider gave %1 (range %2 to %3): using %4", value, low, high, fallback), LogLevel.WARNING);
		}

		DiagMenu.SetRangeValue(id, fallback);
		return fallback;
	}

	//------------------------------------------------------------------------------------------------
	//! Four times a second: read the setting and hand the flag out
	protected static void KeepTick()
	{
		ArmaReforgerScripted game = GetGame();
		if (!game || !s_aKeep || PLAY_WITHOUT_FLAG)
			return;

		BaseWorld world = game.GetWorld();
		if (!world)
			return;

		SightCheck(world);
		if (s_bForceDiag)
		{
			s_iKeepCap = SliderValue(SCR_DebugMenuID.SP_TUNNELS_KEEP_CAP, 0, CAP_ALL, CAP_DEFAULT);
			s_bKeepRelink = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_KEEP_RELINK);
			s_iViewHalf = SliderValue(SCR_DebugMenuID.SP_TUNNELS_KEEP_FOV, 20, 180, FOV_DEFAULT);
		}

		vector view[4];
		world.GetCurrentCamera(view);
		KeepUpdate(view, world);
	}

	//------------------------------------------------------------------------------------------------
	//! Where this piece's openings are in the world (every bone but the root), and its box
	protected void ReadShape()
	{
		m_aOpenings.Clear();
		m_aLinks.Clear();
		IEntity owner = GetOwner();
		if (!owner)
			return;

		owner.GetWorldBounds(m_vWorldMins, m_vWorldMaxs);
		Animation anim = owner.GetAnimation();
		if (!anim)
			return;

		array<string> names = {};
		anim.GetBoneNames(names);
		foreach (string bone : names)
		{
			if (bone == "Scene_Root")
				continue;

			vector mat[4];
			if (anim.GetBoneMatrix(anim.GetBoneIndex(bone), mat))
				m_aOpenings.Insert(owner.CoordToParent(mat[3]));
		}
	}

	//------------------------------------------------------------------------------------------------
	protected static void Join(SP_TunnelExposureComponent a, SP_TunnelExposureComponent b)
	{
		if (a == b || a.m_aLinks.Contains(b))
			return;

		a.m_aLinks.Insert(b);
		b.m_aLinks.Insert(a);
		s_iJoins++;
	}

	//------------------------------------------------------------------------------------------------
	protected static bool BoxesTouch(SP_TunnelExposureComponent a, SP_TunnelExposureComponent b)
	{
		for (int i = 0; i < 3; i++)
		{
			if (a.m_vWorldMins[i] > b.m_vWorldMaxs[i] || b.m_vWorldMins[i] > a.m_vWorldMaxs[i])
				return false;
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! Which pieces are joined: openings that meet, found through a grid of 1 m cells. A piece without readable openings is joined
	//! to whatever its box touches, so it can't fall out of the network
	protected static void BuildLinks(notnull array<SP_TunnelExposureComponent> pieces)
	{
		s_iJoins = 0;
		s_iNoOpenings = 0;
		foreach (SP_TunnelExposureComponent piece : pieces)
		{
			piece.ReadShape();
		}

		map<string, int> cells = new map<string, int>();
		array<ref array<int>> owners = {};
		array<ref array<vector>> points = {};
		foreach (int p, SP_TunnelExposureComponent mine : pieces)
		{
			if (mine.m_aOpenings.IsEmpty())
			{
				s_iNoOpenings++;
				foreach (SP_TunnelExposureComponent other : pieces)
				{
					if (BoxesTouch(mine, other))
						Join(mine, other);
				}

				continue;
			}

			foreach (vector opening : mine.m_aOpenings)
			{
				int cx = Math.Floor(opening[0]);
				int cy = Math.Floor(opening[1]);
				int cz = Math.Floor(opening[2]);
				for (int dx = -1; dx <= 1; dx++)
				{
					for (int dy = -1; dy <= 1; dy++)
					{
						for (int dz = -1; dz <= 1; dz++)
						{
							int found;
							if (!cells.Find(string.Format("%1:%2:%3", cx + dx, cy + dy, cz + dz), found))
								continue;

							foreach (int n, vector there : points[found])
							{
								if (vector.Distance(there, opening) <= KEEP_JOINT)
									Join(mine, pieces[owners[found][n]]);
							}
						}
					}
				}

				string key = string.Format("%1:%2:%3", cx, cy, cz);
				int index;
				if (!cells.Find(key, index))
				{
					array<int> cellOwners = {};
					array<vector> cellPoints = {};
					index = owners.Insert(cellOwners);
					points.Insert(cellPoints);
					cells.Insert(key, index);
				}

				owners[index].Insert(p);
				points[index].Insert(opening);
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! How far outside this piece's box a point is (0: inside)
	protected float Outside(vector point)
	{
		float sum = 0;
		for (int i = 0; i < 3; i++)
		{
			float d = Math.Max(Math.Max(m_vWorldMins[i] - point[i], point[i] - m_vWorldMaxs[i]), 0);
			sum += d * d;
		}

		return Math.Sqrt(sum);
	}

	//------------------------------------------------------------------------------------------------
	//! The piece a ray from the eye hits first (null: none of ours). reached: how far the ray got, metres
	protected static SP_TunnelExposureComponent SightRay(BaseWorld world, vector eye, vector dir, float length, IEntity me, out float reached)
	{
		TraceParam trace = new TraceParam();
		trace.Start = eye;
		trace.End = eye + dir * length;
		trace.Flags = TraceFlags.ENTS;
		trace.Exclude = me;
		reached = world.TraceMove(trace, null) * length;
		IEntity hit = trace.TraceEnt;
		while (hit && !hit.FindComponent(SP_TunnelExposureComponent))
		{
			hit = hit.GetParent();
		}

		if (!hit)
			return null;

		return SP_TunnelExposureComponent.Cast(hit.FindComponent(SP_TunnelExposureComponent));
	}

	//------------------------------------------------------------------------------------------------
	//! Does any part of the piece lie within the view cone? Its openings and the middle of its box, or the box reaching into it
	protected bool InView(vector view[4], float cone)
	{
		foreach (vector opening : m_aOpenings)
		{
			vector toOpening = opening - view[3];
			if (vector.Dot(toOpening, view[2]) >= cone * toOpening.Length())
				return true;
		}

		vector to = (m_vWorldMins + m_vWorldMaxs) * 0.5 - view[3];
		return vector.Dot(to, view[2]) >= cone * to.Length();
	}

	//------------------------------------------------------------------------------------------------
	//! What can be seen right now, marked with the time: a fan of rays across the view (shifted a little each time, so slivers
	//! are found too), a ring of rays all round (for turning), and one through every doorway in front. A hidden piece still has its
	//! collider, so the rays find it whether or not it is being drawn
	protected static void MarkSeen(vector view[4], BaseWorld world, notnull array<SP_TunnelExposureComponent> pieces, int now)
	{
		vector eye = view[3];
		IEntity me = SCR_PlayerController.GetLocalControlledEntity();
		s_iSightPhase = (s_iSightPhase + 1) % 4;
		float shift = s_iSightPhase * 0.25;
		float reached;
		SP_TunnelExposureComponent seen;
		for (int ix = -4; ix <= 4; ix++)
		{
			for (int iy = -2; iy <= 2; iy++)
			{
				vector fan = view[2] + view[0] * Math.Tan((ix + shift - 0.375) * 12 * Math.DEG2RAD) + view[1] * Math.Tan((iy + shift - 0.375) * 11 * Math.DEG2RAD);
				fan.Normalize();
				seen = SightRay(world, eye, fan, SIGHT_RANGE, me, reached);
				if (seen)
					seen.m_iSeenAt = now;
			}
		}

		for (int turn = 0; turn < 8; turn++)
		{
			float around = (turn * 45 + shift * 45) * Math.DEG2RAD;
			vector ring = Vector(Math.Sin(around), 0, Math.Cos(around));
			seen = SightRay(world, eye, ring, SIGHT_RANGE, me, reached);
			if (seen)
				seen.m_iSeenAt = now;
		}

		foreach (SP_TunnelExposureComponent piece : pieces)
		{
			foreach (vector opening : piece.m_aOpenings)
			{
				vector to = opening - eye;
				float away = to.Length();
				if (away > OPENING_RANGE || away < 0.5 || vector.Dot(to, view[2]) < 0.35 * away)
					continue;

				vector through = to * (1 / away);
				seen = SightRay(world, eye, through, away + 60, me, reached);
				if (reached < away - 0.7)
					continue;			// a wall before the doorway

				piece.m_iSeenAt = now;
				if (seen)
					seen.m_iSeenAt = now;
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! With the setting at the top every piece keeps its flag. Below, the setting's number of flags go to pieces connected to the
	//! camera's along the openings: the pieces the camera is in, the ones joined to those (a quick turn), then by distance along the
	//! tunnels, what is in view first (out of view counts as much further; hit by a ray, as nearer). Only changes are sent
	protected static void KeepUpdate(vector view[4], BaseWorld world)
	{
		vector eye = view[3];
		array<SP_TunnelExposureComponent> pieces = {};
		foreach (SP_TunnelExposureComponent each : s_aKeep)
		{
			if (each && each.GetOwner() && each.GetOwner().GetWorld() == world)
				pieces.Insert(each);
		}

		if (s_iKeepCap >= CAP_ALL)
		{
			foreach (SP_TunnelExposureComponent whole : pieces)
			{
				if (!whole.m_bKept)
					whole.SetKept(true);
			}

			return;
		}

		if (s_bLinksDirty)
		{
			BuildLinks(pieces);
			s_bLinksDirty = false;
		}

		int now = System.GetTickCount();
		MarkSeen(view, world, pieces, now);

		// the walk along the openings: where it starts, and how far every piece is along it
		s_iKeepRun++;
		array<SP_TunnelExposureComponent> open = {};
		foreach (SP_TunnelExposureComponent inside : pieces)
		{
			if (inside.Outside(eye) <= 0.5)
				open.Insert(inside);
		}

		if (open.IsEmpty())
		{
			foreach (SP_TunnelExposureComponent near : pieces)
			{
				if (near.Outside(eye) <= KEEP_OUTSIDE)
					open.Insert(near);
			}
		}

		array<SP_TunnelExposureComponent> starts = {};
		starts.Copy(open);
		foreach (SP_TunnelExposureComponent first : open)
		{
			first.m_iSeen = s_iKeepRun;
			first.m_fPath = first.Outside(eye);
		}

		while (!open.IsEmpty())
		{
			int best = 0;
			foreach (int i, SP_TunnelExposureComponent candidate : open)
			{
				if (candidate.m_fPath < open[best].m_fPath)
					best = i;
			}

			SP_TunnelExposureComponent current = open[best];
			open.Remove(best);
			vector middle = (current.m_vWorldMins + current.m_vWorldMaxs) * 0.5;
			foreach (SP_TunnelExposureComponent next : current.m_aLinks)
			{
				if (!next)
					continue;

				float path = current.m_fPath + vector.Distance(middle, (next.m_vWorldMins + next.m_vWorldMaxs) * 0.5);
				if (path > KEEP_PATH)
					continue;

				if (next.m_iSeen != s_iKeepRun)
				{
					next.m_iSeen = s_iKeepRun;
					next.m_fPath = path;
					open.Insert(next);
				}
			}
		}

		// rank everyone who could get a flag (smaller first)
		array<SP_TunnelExposureComponent> order = {};
		array<float> ranks = {};
		array<int> tiers = {};
		float cone = Math.Cos(s_iViewHalf * Math.DEG2RAD);
		foreach (SP_TunnelExposureComponent piece : pieces)
		{
			bool here = starts.Contains(piece) && piece.Outside(eye) <= 0.5;
			bool beside = false;
			foreach (SP_TunnelExposureComponent link : piece.m_aLinks)
			{
				if (link && starts.Contains(link) && link.Outside(eye) <= 0.5)
					beside = true;
			}

			bool walked = piece.m_iSeen == s_iKeepRun;
			bool seen = now - piece.m_iSeenAt < SEEN_FOR_MS;
			int tier = -1;
			float rank = 0;
			if (here)
			{
				tier = 0;
			}
			else if (beside)
			{
				tier = 1;
				rank = 1 + piece.Outside(eye) * 0.001;
			}
			else if (walked)
			{
				float along = piece.m_fPath;
				if (seen)
					along = along * SEEN_FACTOR;

				tier = 2;
				if (!piece.InView(view, cone))
				{
					tier = 3;
					along = along * OUT_OF_VIEW + OUT_OF_VIEW_ADD;
				}

				rank = 10 + along;
			}
			else if (seen)
			{
				tier = 4;		// in sight although not joined along the openings: after everything that is
				rank = 100000 + piece.Outside(eye);
			}

			if (tier < 0)
				continue;

			int at = ranks.Count();
			while (at > 0 && ranks[at - 1] > rank)
			{
				at--;
			}

			ranks.InsertAt(rank, at);
			order.InsertAt(piece, at);
			tiers.InsertAt(tier, at);
		}

		int kept = Math.Min(s_iKeepCap, order.Count());
		int atCamera = 0;
		int nextTo = 0;
		int inView = 0;
		int outOfView = 0;
		int unjoined = 0;
		int viewLeftOut = 0;
		for (int k = 0; k < order.Count(); k++)
		{
			if (k >= kept)
			{
				if (tiers[k] <= 2)
					viewLeftOut++;

				continue;
			}

			order[k].m_iDone = s_iKeepRun;
			if (tiers[k] == 0)
				atCamera++;
			else if (tiers[k] == 1)
				nextTo++;
			else if (tiers[k] == 2)
				inView++;
			else if (tiers[k] == 3)
				outOfView++;
			else
				unjoined++;
		}

		// take flags off before putting new ones on, so there are never more than the setting
		foreach (SP_TunnelExposureComponent drop : pieces)
		{
			if (drop.m_bKept && drop.m_iDone != s_iKeepRun)
				drop.SetKept(false);
		}

		for (int n = 0; n < kept; n++)
		{
			if (!order[n].m_bKept)
				order[n].SetKept(true);
		}

		if (now - s_iChoiceLogged >= COUNT_LOG_MS)
		{
			s_iChoiceLogged = now;
			Print(string.Format("SP_TunnelKeep: flags go to %1 at the camera, %2 next to it, %3 in view, %4 out of view, %5 seen but not joined; in view but left without: %6 (cone %7 deg)", atCamera, nextTo, inView, outOfView, unjoined, viewLeftOut, s_iViewHalf));
		}
	}

	//------------------------------------------------------------------------------------------------
	//! One of the scene tree flags switched on or back to how the piece spawned
	protected void SwitchFlag(EntityFlags flag, bool on, bool add)
	{
		IEntity owner = GetOwner();
		if (!owner)
			return;

		bool had = (m_iStartFlags & flag) != 0;
		bool want = had;
		if (on)
			want = add;

		if (want)
			owner.SetFlags(flag, false);
		else
			owner.ClearFlags(flag, false);
	}

	//------------------------------------------------------------------------------------------------
	protected void Relink()
	{
		IEntity owner = GetOwner();
		if (!owner)
			return;

		owner.SetFlags(EntityFlags.UPDATE_LINK, false);
		owner.Update();
	}

	//------------------------------------------------------------------------------------------------
	//! A probe standing within a tunnel piece's box is one of ours (the pieces' probes are not linked to them as children)
	protected static bool CollectProbe(IEntity entity)
	{
		EnvironmentProbeEntity probe = EnvironmentProbeEntity.Cast(entity);
		if (!probe)
			return true;

		s_iProbesSeen++;
		vector at = entity.GetOrigin();
		foreach (SP_TunnelExposureComponent piece : s_aKeep)
		{
			if (!piece || !piece.GetOwner())
				continue;

			vector mins, maxs;
			piece.GetOwner().GetWorldBounds(mins, maxs);
			piece.m_vWorldMins = mins;
			piece.m_vWorldMaxs = maxs;
			if (piece.Outside(at) <= 0.5)
			{
				s_aProbesFound.Insert(probe);
				break;
			}
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! Once a second: the dark probes within 200 m of the camera off or on again, as the switch says
	protected static void ReadProbeDiag()
	{
		if (!s_bForceDiag || !s_aKeep)
			return;

		bool off = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_PROBES_OFF);
		if (off == s_bProbesOff)
			return;

		s_bProbesOff = off;
		ArmaReforgerScripted game = GetGame();
		if (!game || !game.GetWorld())
			return;

		vector view[4];
		game.GetWorld().GetCurrentCamera(view);
		s_aProbesFound = {};
		s_iProbesSeen = 0;
		game.GetWorld().QueryEntitiesBySphere(view[3], 200, CollectProbe, null, EQueryEntitiesFlags.ALL);
		foreach (EnvironmentProbeEntity probe : s_aProbesFound)
		{
			if (!probe)
				continue;

			if (off)
				probe.Deactivate();
			else
				probe.Activate();
		}

		string state = "ON";
		if (off)
			state = "OFF";

		Print(string.Format("SP_TunnelKeep: %1 dark probes switched %2 (probes met within 200 m: %3)", s_aProbesFound.Count(), state, s_iProbesSeen));
	}

	//------------------------------------------------------------------------------------------------
	//! Once a second: the scene tree flags as the switches say
	protected static void ReadFlagDiag()
	{
		if (!s_bForceDiag || !s_aKeep)
			return;

		bool noStatic = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_NOSTATIC);
		bool active = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_ACTIVE);
		bool noTree = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_NOTREE);
		s_bFlagRelink = DiagMenu.GetBool(SCR_DebugMenuID.SP_TUNNELS_FLAG_RELINK);
		bool changed = noStatic != s_bFlagNoStatic || active != s_bFlagActive || noTree != s_bFlagNoTree;
		s_bFlagNoStatic = noStatic;
		s_bFlagActive = active;
		s_bFlagNoTree = noTree;
		foreach (SP_TunnelExposureComponent piece : s_aKeep)
		{
			if (!piece)
				continue;

			if (changed)
			{
				piece.SwitchFlag(EntityFlags.STATIC, noStatic, false);
				piece.SwitchFlag(EntityFlags.ACTIVE, active, true);
				piece.SwitchFlag(EntityFlags.NO_TREE, noTree, true);
			}

			if (changed || s_bFlagRelink)
				piece.Relink();
		}

		if (changed)
			Print(string.Format("SP_TunnelKeep: flags switched: STATIC removed %1, ACTIVE added %2, NO_TREE added %3", noStatic, active, noTree));
	}

	//------------------------------------------------------------------------------------------------
	//! Rays across the view: the first piece a ray hits can be seen, so the engine has to have drawn it. One it did not is the
	//! vanishing itself, caught in the act
	protected static void SightCheck(BaseWorld world)
	{
		vector view[4];
		world.GetCurrentCamera(view);
		IEntity me = SCR_PlayerController.GetLocalControlledEntity();
		int now = System.GetTickCount();
		for (int ix = -2; ix <= 2; ix++)
		{
			for (int iy = -1; iy <= 1; iy++)
			{
				float side = ix * 14;
				float rise = iy * 12;
				vector dir = view[2] + view[0] * Math.Tan(side * Math.DEG2RAD) + view[1] * Math.Tan(rise * Math.DEG2RAD);
				dir.Normalize();
				TraceParam trace = new TraceParam();
				trace.Start = view[3];
				trace.End = view[3] + dir * 150;
				trace.Flags = TraceFlags.ENTS;
				trace.Exclude = me;
				float share = world.TraceMove(trace, null);
				IEntity hit = trace.TraceEnt;
				while (hit && !hit.FindComponent(SP_TunnelExposureComponent))
				{
					hit = hit.GetParent();
				}

				if (!hit)
					continue;

				s_iSightRays++;
				if (hit.IsRendered())
					continue;

				s_iSightMissed++;
				if (now - s_iMissLogged < 1000)
					continue;

				s_iMissLogged = now;
				string name = "?";
				EntityPrefabData data = hit.GetPrefabData();
				if (data)
					name = FilePath.StripPath(data.GetPrefabName());

				Print(string.Format("SP_TunnelKeep: IN VIEW BUT NOT DRAWN: %1, %2 m away, %3 deg to the side, %4 deg up, flag %5", name, Math.Round(share * 150), side, rise, EngineHasFlag(hit)));
			}
		}

		if (now - s_iSightReported < COUNT_LOG_MS || !s_aKeep)
			return;

		s_iSightReported = now;
		int drawn = 0;
		int all = 0;
		foreach (SP_TunnelExposureComponent piece : s_aKeep)
		{
			if (!piece || !piece.GetOwner() || piece.GetOwner().GetWorld() != world)
				continue;

			all++;
			if (piece.GetOwner().IsRendered())
				drawn++;
		}

		Print(string.Format("SP_TunnelKeep: sight rays on pieces %1, of these not drawn %2; engine drew %3 of %4 pieces last frame", s_iSightRays, s_iSightMissed, drawn, all));
		s_iSightRays = 0;
		s_iSightMissed = 0;
	}

	//------------------------------------------------------------------------------------------------
	protected static bool EngineHasFlag(IEntity entity)
	{
		return (entity.GetFlags() & EntityFlags.FEATURE) != 0;
	}

	//------------------------------------------------------------------------------------------------
	//! Names the piece in the middle of the view, then counts the pieces that have lost the flag and sets it again
	protected static void CheckFlags()
	{
		ArmaReforgerScripted game = GetGame();
		if (!game || !s_aKeep)
			return;

		BaseWorld world = game.GetWorld();
		if (!world || s_bFeatureOff)
			return;

		LogLookedAt(world);
		ForceSlow(world);
		ReadFlagDiag();
		ReadProbeDiag();
		int all = 0;
		int lost = 0;
		int held = 0;
		foreach (SP_TunnelExposureComponent piece : s_aKeep)
		{
			if (!piece || !piece.GetOwner() || piece.GetOwner().GetWorld() != world)
				continue;

			all++;
			if (PLAY_WITHOUT_FLAG)
			{
				if (EngineHasFlag(piece.GetOwner()))
					lost++;			// in the test: pieces that have it although nothing here set it

				continue;
			}

			if (!piece.m_bKept)
			{
				held++;			// meant to be without (the setting)
				continue;
			}

			if (EngineHasFlag(piece.GetOwner()))
				continue;

			lost++;
			piece.GetOwner().SetFlags(EntityFlags.FEATURE, false);
		}

		// how many the engine says have the flag (in the test without it: lost counts those that have it all the same)
		int flagged = all - lost - held;
		if (PLAY_WITHOUT_FLAG)
			flagged = lost;

		// the count, once a second
		string note = "";
		if (PLAY_WITHOUT_FLAG)
			note = " (TEST: none are given the flag)";
		else if (lost > 0)
			note = string.Format(" (%1 had LOST it: set again)", lost);

		vector eyeNow[4];
		world.GetCurrentCamera(eyeNow);
		float under = world.GetSurfaceY(eyeNow[3][0], eyeNow[3][2]) - eyeNow[3][1];
		Print(string.Format("SP_TunnelKeep: no-cull flag on %1 of %2 pieces (setting %3, re-show %4)%5, camera %6 m under the ground", flagged, all, s_iKeepCap, s_bKeepRelink, note, Math.Round(under)));

		int now = System.GetTickCount();
		if (all != s_iKeepReported || flagged != s_iFlagReported || now - s_iCountLogged >= COUNT_LOG_MS)
		{
			s_iKeepReported = all;
			s_iFlagReported = flagged;
			s_iCountLogged = now;
			vector view[4];
			world.GetCurrentCamera(view);
			float flaggedTo = 0;
			float unflaggedFrom = 100000;
			foreach (SP_TunnelExposureComponent measured : s_aKeep)
			{
				if (!measured || !measured.GetOwner() || measured.GetOwner().GetWorld() != world)
					continue;

				vector mins, maxs;
				measured.GetOwner().GetWorldBounds(mins, maxs);
				measured.m_vWorldMins = mins;
				measured.m_vWorldMaxs = maxs;
				float straight = measured.Outside(view[3]);
				if (EngineHasFlag(measured.GetOwner()))
					flaggedTo = Math.Max(flaggedTo, straight);
				else
					unflaggedFrom = Math.Min(unflaggedFrom, straight);
			}

			Print(string.Format("SP_TunnelKeep: in a straight line: flagged pieces up to %1 m, nearest piece without the flag %2 m (100000: none)", Math.Round(flaggedTo), Math.Round(unflaggedFrom)));
		}
	}

	//------------------------------------------------------------------------------------------------
	//! A piece that isn't drawn still has its collider, so looking into the hole where one vanished names it
	protected static void LogLookedAt(BaseWorld world)
	{
		vector view[4];
		world.GetCurrentCamera(view);
		TraceParam trace = new TraceParam();
		trace.Start = view[3];
		trace.End = view[3] + view[2] * 300;
		trace.Flags = TraceFlags.ENTS;
		trace.Exclude = SCR_PlayerController.GetLocalControlledEntity();
		float share = world.TraceMove(trace, null);
		IEntity hit = trace.TraceEnt;
		while (hit && !hit.FindComponent(SP_TunnelExposureComponent))
		{
			hit = hit.GetParent();
		}

		if (!hit)
			return;

		string name = "?";
		EntityPrefabData data = hit.GetPrefabData();
		if (data)
			name = FilePath.StripPath(data.GetPrefabName());

		string state = "has the flag";
		if (!EngineHasFlag(hit))
			state = "does NOT have the flag";

		string key = name + state + hit.GetOrigin().ToString();
		if (key == s_sLookedAt)
			return;

		s_sLookedAt = key;
		SP_TunnelExposureComponent piece = SP_TunnelExposureComponent.Cast(hit.FindComponent(SP_TunnelExposureComponent));
		vector mins, maxs;
		hit.GetWorldBounds(mins, maxs);
		piece.m_vWorldMins = mins;
		piece.m_vWorldMaxs = maxs;
		string along = "";
		if (s_iKeepCap < CAP_ALL)
		{
			if (piece.m_iDone == s_iKeepRun)
				along = string.Format(", %1 m along the tunnels, %2 joined pieces", Math.Round(piece.m_fPath), piece.m_aLinks.Count());
			else
				along = string.Format(", not within the setting along the joins, %1 joined pieces", piece.m_aLinks.Count());
		}

		vector at = hit.GetOrigin();
		float deep = world.GetSurfaceY(at[0], at[2]) - at[1];
		Print(string.Format("SP_TunnelKeep: looking at %1, %2 m away (its box %3 m): the engine says it %4%5, piece %6 m under the ground", name, Math.Round(share * 300), Math.Round(piece.Outside(view[3])), state, along, Math.Round(deep)));
	}

	//------------------------------------------------------------------------------------------------
	// Live tuning in play mode: diag menu (Win+Alt) > Tunnels. The slider starts at the prefab's value; moving it
	// overrides every piece at once, so the right value can be found standing in the cave.
	// ids come from the vanilla diag enum (modded below): free numbers of our own crashed the engine
	protected static const int DIAG_MENU = SCR_DebugMenuID.SP_TUNNELS_MENU;
	protected static const int DIAG_GAIN = SCR_DebugMenuID.SP_TUNNELS_GAIN;
	protected static const int DIAG_NO_GRADE = SCR_DebugMenuID.SP_TUNNELS_NO_GRADE;
	protected static const int DIAG_LOG = SCR_DebugMenuID.SP_TUNNELS_LOG;
	protected static const int DIAG_NO_FEATURE = SCR_DebugMenuID.SP_TUNNELS_NO_FEATURE;
	protected static const int DIAG_HOLD_OFF = SCR_DebugMenuID.SP_TUNNELS_HOLD_OFF;
	protected static const int DIAG_TORCH_OFF = SCR_DebugMenuID.SP_TUNNELS_TORCH_OFF;
	protected static bool s_bDiag;
	protected static float s_fDiagStart;

	protected static void RegisterDiag()
	{
		if (s_bDiag)
			return;

		s_bDiag = true;
		s_fDiagStart = s_fGain;
		DiagMenu.RegisterMenu(DIAG_MENU, "Tunnels", "");
		DiagMenu.RegisterRange(DIAG_GAIN, "", "Exposure gain", "Tunnels", string.Format("0.001, 0.5, %1, 0.001", s_fGain));
		DiagMenu.RegisterBool(DIAG_NO_GRADE, "", "Colour grade off", "Tunnels");
		DiagMenu.RegisterBool(DIAG_LOG, "", "Log exposure", "Tunnels");
		DiagMenu.RegisterBool(DIAG_NO_FEATURE, "", "No-cull flag off (compare FPS)", "Tunnels");
		DiagMenu.RegisterBool(DIAG_HOLD_OFF, "", "Exposure hold off (engine + probes only)", "Tunnels");
		DiagMenu.RegisterBool(DIAG_TORCH_OFF, "", "Flashlight boost off", "Tunnels");
	}

	//! Diag 'No-cull flag off': takes EntityFlags.FEATURE off every piece that had it (and back on), to compare frame rates
	protected static void FeatureSwitch()
	{
		if (!s_bDiag)
			return;

		bool off = DiagMenu.GetBool(DIAG_NO_FEATURE);
		if (off == s_bFeatureOff)
			return;

		s_bFeatureOff = off;
		foreach (SP_TunnelExposureComponent piece : s_aPieces)
		{
			if (!piece || !piece.m_bKeepRendered || !piece.GetOwner())
				continue;

			if (off)
				piece.GetOwner().ClearFlags(EntityFlags.FEATURE, false);
			else
				piece.GetOwner().SetFlags(EntityFlags.FEATURE, false);
		}

		string state = "ON";
		if (off)
			state = "OFF";

		Print(string.Format("SP_TunnelExposure: no-cull flag %1 on %2 pieces", state, s_aPieces.Count()));
	}

	//! The gain in use: the diag slider once it has been moved, else the prefab's
	protected static float Gain()
	{
		if (s_bDiag && s_fDiagGain > 0.001 && Math.AbsFloat(s_fDiagGain - s_fDiagStart) > 0.0001)
			return s_fDiagGain;

		return s_fGain;
	}

	//! Reads the diag menu (called from the 10 Hz scan only)
	protected static void ReadDiag()
	{
		if (!s_bDiag)
			return;

		s_fDiagGain = DiagMenu.GetRangeValue(DIAG_GAIN);
		s_bDiagNoGrade = DiagMenu.GetBool(DIAG_NO_GRADE);
		s_bDiagLog = DiagMenu.GetBool(DIAG_LOG);
		s_bDiagHoldOff = DiagMenu.GetBool(DIAG_HOLD_OFF);
		s_bDiagTorchOff = DiagMenu.GetBool(DIAG_TORCH_OFF);
	}

	//------------------------------------------------------------------------------------------------
	override void OnDelete(IEntity owner)
	{
		if (s_aKeep)
		{
			s_aKeep.RemoveItem(this);
			s_bLinksDirty = true;
			if (s_aKeep.IsEmpty())
			{
				s_aKeep = null;
				ArmaReforgerScripted running = GetGame();
				if (running && running == s_KeepGame)
				{
					running.GetCallqueue().Remove(CheckFlags);
					running.GetCallqueue().Remove(ForceTick);
					running.GetCallqueue().Remove(KeepTick);
					s_KeepGame = null;
				}
			}
		}

		if (!s_aPieces)
			return;

		s_aPieces.RemoveItem(this);
		if (s_LastPiece == this)
			s_LastPiece = null;
		if (s_aPieces.IsEmpty())
		{
			s_aPieces = null;
			ArmaReforgerScripted game = GetGame();
			if (game)
			{
				game.GetCallqueue().Remove(Expose);
				Let(game.GetWorld());
				DropManProbes();
				DropTorchLights();
				s_bTorchOn = false;
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Is the player's own flashlight on, while the camera is underground? (checked every 0.3 s)
	protected static void CheckTorch(int now)
	{
		if (now < s_iNextTorchCheck)
			return;

		s_iNextTorchCheck = now + 300;
		s_bTorchOn = false;
		if (s_fDark < 0.3 || s_bDiagTorchOff)
			return;

		IEntity me = SCR_PlayerController.GetLocalControlledEntity();
		if (!me)
			return;

		SCR_GadgetManagerComponent gadgets = SCR_GadgetManagerComponent.GetGadgetManager(me);
		if (!gadgets)
			return;

		array<SCR_GadgetComponent> torches = gadgets.GetGadgetsByType(EGadgetType.FLASHLIGHT);
		foreach (SCR_GadgetComponent torch : torches)
		{
			if (torch && torch.IsToggledOn())
				s_bTorchOn = true;
		}
	}

	//------------------------------------------------------------------------------------------------
	//! The spill and the beam follow the view every frame (only while the torch is on)
	protected static void UpdateTorch(vector camera[4])
	{
		vector spillAt = camera[3] + camera[2] * 0.6 + "0 0.2 0";
		vector beamAt = camera[3] + camera[2] * 0.3 - "0 0.15 0";
		if (s_bTorchOn && !s_Spill)
		{
			s_Spill = LightEntity.CreateLight(LightType.POINT, 0, 5, Color.FromRGBA(255, 235, 200, 255), SPILL_LV, spillAt);
			s_Beam = LightEntity.CreateLight(LightType.SPOT, 0, 25, Color.FromRGBA(255, 240, 215, 255), BEAM_LV, beamAt, camera[2]);
			if (s_Spill)
				s_Spill.SetLensFlareType(LightLensFlareType.Disabled);

			if (s_Beam)
			{
				s_Beam.SetLensFlareType(LightLensFlareType.Disabled);
				s_Beam.SetConeAngle(BEAM_CONE);
				s_Beam.SetConeAngleAttenuation(0.4);
			}
		}
		else if (!s_bTorchOn && s_Spill)
		{
			DropTorchLights();
		}

		if (s_Spill)
		{
			s_Spill.SetOrigin(spillAt);
			s_Spill.Update();
		}

		if (s_Beam)
		{
			s_Beam.SetOrigin(beamAt);
			s_Beam.SetLightDirection(camera[2]);
			s_Beam.Update();
		}
	}

	//------------------------------------------------------------------------------------------------
	protected static void DropTorchLights()
	{
		if (s_Spill)
			delete s_Spill;

		s_Spill = null;
		if (s_Beam)
			delete s_Beam;

		s_Beam = null;
	}

	//------------------------------------------------------------------------------------------------
	//! How dark it is at this spot: inside any piece (an entrance by depth), else 0
	protected static float DarkAt(vector pos, BaseWorld world)
	{
		foreach (SP_TunnelExposureComponent piece : s_aPieces)
		{
			if (!piece)
				continue;

			float d = piece.DarknessAt(pos, world);
			if (d > 0)
				return d;
		}

		return 0;
	}

	//------------------------------------------------------------------------------------------------
	//! Twice a second: soldiers within 40 m of the camera who are underground get a black probe, the others give theirs
	//! back. Local only (each machine for its own picture), nothing is sent.
	protected static void ManProbeTick(BaseWorld world, vector eye)
	{
		if (!s_aProbeMen)
		{
			s_aProbeMen = {};
			s_aManProbes = {};
		}

		for (int i = s_aProbeMen.Count() - 1; i >= 0; i--)
		{
			IEntity carrier = s_aProbeMen[i];
			IEntity carried = s_aManProbes[i];
			if (carrier && carried && DarkAt(carrier.GetOrigin() + "0 0.9 0", world) > 0)
				continue;

			if (carried)
				SCR_EntityHelper.DeleteEntityAndChildren(carried);

			s_aProbeMen.Remove(i);
			s_aManProbes.Remove(i);
		}

		SP_TunnelExposureComponent any = s_LastPiece;
		if (!any)
		{
			foreach (SP_TunnelExposureComponent piece : s_aPieces)
			{
				if (piece)
				{
					any = piece;
					break;
				}
			}
		}

		if (any)
			world.QueryEntitiesBySphere(eye, 40, any.OnManQuery, null, EQueryEntitiesFlags.DYNAMIC);
	}

	//------------------------------------------------------------------------------------------------
	protected bool OnManQuery(IEntity entity)
	{
		ChimeraCharacter man = ChimeraCharacter.Cast(entity);
		if (!man || s_aProbeMen.Contains(man))
			return true;

		BaseWorld world = man.GetWorld();
		if (!world || DarkAt(man.GetOrigin() + "0 0.9 0", world) <= 0)
			return true;

		if (!s_ManProbeRes)
			s_ManProbeRes = Resource.Load(MAN_PROBE);

		if (!s_ManProbeRes || !s_ManProbeRes.IsValid())
			return false;

		EntitySpawnParams params = new EntitySpawnParams();
		params.TransformMode = ETransformMode.WORLD;
		params.Transform[3] = man.GetOrigin() + "0 1 0";
		IEntity probe = GetGame().SpawnEntityPrefabLocal(s_ManProbeRes, world, params);
		if (!probe)
			return true;

		man.AddChild(probe, -1);
		vector offset[4];
		Math3D.MatrixIdentity4(offset);
		offset[3] = Vector(0, 1, 0);
		probe.SetLocalTransform(offset);
		probe.Update();
		s_aProbeMen.Insert(man);
		s_aManProbes.Insert(probe);
		return true;
	}

	//------------------------------------------------------------------------------------------------
	protected static void DropManProbes()
	{
		if (!s_aManProbes)
			return;

		foreach (IEntity carried : s_aManProbes)
		{
			if (carried)
				SCR_EntityHelper.DeleteEntityAndChildren(carried);
		}

		s_aManProbes.Clear();
		s_aProbeMen.Clear();
	}

	//------------------------------------------------------------------------------------------------
	//! 1 inside this piece, 0 outside it; in an entrance, by how deep under the ground
	protected float DarknessAt(vector pos, BaseWorld world)
	{
		if (vector.DistanceSq(m_vOrigin, pos) > 400)
			return 0;

		IEntity owner = GetOwner();
		if (!owner)
			return 0;

		vector local = owner.CoordToLocal(pos);
		for (int i = 0; i < 3; i++)
		{
			if (local[i] < m_vMins[i] || local[i] > m_vMaxs[i])
				return 0;
		}

		if (!m_bEntrance)
			return 1;

		float depth = world.GetSurfaceY(pos[0], pos[2]) - pos[1];
		return Math.Clamp((depth - 0.5) / 2.5, 0, 1);
	}

	//------------------------------------------------------------------------------------------------
	//! Every frame
	protected static void Expose()
	{
		ArmaReforgerScripted game = GetGame();
		if (!game || !s_aPieces)
			return;

		BaseWorld world = game.GetWorld();
		if (!world)
			return;

		int now = System.GetTickCount();
		float frame = Math.Clamp((now - s_iLastFrame) * 0.001, 0, 0.1);
		s_iLastFrame = now;

		vector view[4];
		world.GetCurrentCamera(view);
		int camera = world.GetCurrentCameraId();
		if (s_iHeldCamera >= 0 && s_iHeldCamera != camera)
			Let(world);

		if (now >= s_iNextScan)
		{
			s_iNextScan = now + 100;
			float found;
			SP_TunnelExposureComponent best;
			if (s_LastPiece)
			{
				found = s_LastPiece.DarknessAt(view[3], world);
				if (found > 0)
					best = s_LastPiece;
			}

			if (found < 1)
			{
				foreach (SP_TunnelExposureComponent piece : s_aPieces)
				{
					if (!piece || piece == s_LastPiece)
						continue;

					float d = piece.DarknessAt(view[3], world);
					if (d > found)
					{
						found = d;
						best = piece;
						if (found >= 1)
							break;
					}
				}
			}

			s_fDark = found;
			s_LastPiece = best;
			ReadDiag();
			FeatureSwitch();
			if (now >= s_iNextManTick)
			{
				s_iNextManTick = now + 500;
				ManProbeTick(world, view[3]);
			}
		}

		float dark = s_fDark;
		CheckTorch(now);
		UpdateTorch(view);
		if (s_bDiagHoldOff)
		{
			// comparison: the engine's own exposure with the dark probes' HDR settings, no hold, no grade
			if (s_iHeldCamera >= 0)
				Let(world);

			return;
		}

		float outside = Math.Log2(s_fOutsideGain);
		float gain = Gain();
		float target = outside + (Math.Log2(gain) - outside) * dark;
		if (s_iHeldCamera < 0)
		{
			float seen = world.GetCameraHDRBrightness(camera);
			if (dark < 0.02)
			{
				// Out in the open: remember what the game's exposure makes of it, to hand back to on the way out
				if (seen > 0.001 && seen < 4)
					s_fOutsideGain = seen;

				return;
			}

			// Walking in: held from where the game's exposure is, so nothing jumps; arriving deep in: straight there
			if (dark > 0.5 || seen < 0.001 || seen > 4)
				s_fHeldStops = target;
			else
				s_fHeldStops = Math.Log2(seen);

			s_iHeldCamera = camera;
			s_iOutSince = 0;
		}

		s_fHeldStops = s_fHeldStops + (target - s_fHeldStops) * Math.Min(1, frame * 5);

		// Back out in the open and level with it: the game's own exposure again
		if (dark <= 0)
		{
			if (s_iOutSince == 0)
				s_iOutSince = now;

			if (now - s_iOutSince > 400 && Math.AbsFloat(s_fHeldStops - outside) < 0.05)
			{
				Let(world);
				return;
			}
		}
		else
		{
			s_iOutSince = 0;
		}

		float send = Math.Pow(2, s_fHeldStops);
		if (s_fSentGain < 0 || Math.AbsFloat(send - s_fSentGain) > s_fSentGain * 0.003)
		{
			world.SetCameraHDRBrightness(camera, send);
			s_fSentGain = send;
		}

		// The sky's haze lies over everything that takes fog, soldiers included (their materials can't switch it off):
		// a gentle grade pulls the darkest tones back to black, in four steps by how far in the camera is
		int step = Math.Round(Math.Clamp(dark, 0, 1) * GRADE_STEPS.Count());
		if (s_bDiagNoGrade)
			step = 0;

		Grade(world, camera, step);
		if (s_bDiagLog && now - s_iLastLog > 1000)
		{
			s_iLastLog = now;
			Print(string.Format("SP_TunnelExposure: gain %1 (prefab %2), held %3, dark %4, grade step %5", gain, s_fGain, Math.Pow(2, s_fHeldStops), dark, step));
		}
	}

	protected static const int GRADE_SLOT = 15;
	protected static const ref array<string> GRADE_STEPS = {"{6E34723529370D85}Assets/Tunnels/TT/Data/TT_Grade_1.emat", "{7812EF9B6FD22828}Assets/Tunnels/TT/Data/TT_Grade_2.emat", "{5C24ECF24988D099}Assets/Tunnels/TT/Data/TT_Grade_3.emat", "{CEEA07629923CFB2}Assets/Tunnels/TT/Data/TT_Grade_4.emat"};
	protected static int s_iGradeStep;
	protected static int s_iGradeCamera = -1;

	//------------------------------------------------------------------------------------------------
	//! The underground grade on this camera at this step (0 off), taken off whichever camera had it before
	protected static void Grade(BaseWorld world, int camera, int step)
	{
		if (!world)
			return;

		if (step == s_iGradeStep && (step == 0 || camera == s_iGradeCamera))
			return;

		if (s_iGradeStep > 0 && s_iGradeCamera >= 0)
			world.SetCameraPostProcessEffect(s_iGradeCamera, GRADE_SLOT, PostProcessEffectType.None, string.Empty);

		s_iGradeStep = 0;
		s_iGradeCamera = -1;
		if (step <= 0 || camera < 0)
			return;

		world.SetCameraPostProcessEffect(camera, GRADE_SLOT, PostProcessEffectType.Colors, GRADE_STEPS[step - 1]);
		s_iGradeStep = step;
		s_iGradeCamera = camera;
	}

	//------------------------------------------------------------------------------------------------
	//! The camera goes back to the game's own exposure, without the grade
	protected static void Let(BaseWorld world)
	{
		if (s_iHeldCamera >= 0 && world)
			world.SetCameraHDRBrightness(s_iHeldCamera, -1);

		Grade(world, -1, 0);
		s_fSentGain = -1;
		s_iHeldCamera = -1;
		s_iOutSince = 0;
	}
}

//! The tunnels' entries in the diag menu (Win+Alt > Tunnels)
modded enum SCR_DebugMenuID
{
	SP_TUNNELS_MENU,
	SP_TUNNELS_GAIN,
	SP_TUNNELS_NO_GRADE,
	SP_TUNNELS_LOG,
	SP_TUNNELS_NO_FEATURE,
	SP_TUNNELS_HOLD_OFF,
	SP_TUNNELS_TORCH_OFF,
	SP_TUNNELS_CULL_MENU,
	SP_TUNNELS_FORCE_UPDATE,
	SP_TUNNELS_FORCE_SHOW,
	SP_TUNNELS_FORCE_MESH,
	SP_TUNNELS_FORCE_LOD,
	SP_TUNNELS_KEEP_CAP,
	SP_TUNNELS_KEEP_RELINK,
	SP_TUNNELS_FLAG_NOSTATIC,
	SP_TUNNELS_FLAG_ACTIVE,
	SP_TUNNELS_FLAG_NOTREE,
	SP_TUNNELS_FLAG_RELINK,
	SP_TUNNELS_KEEP_FOV,
	SP_TUNNELS_PROBES_OFF
}
